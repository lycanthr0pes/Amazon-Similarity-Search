# データ保存と論理スキーマ

## 条件入力順の集約metadata（EXEC-167）

CandidatePlanとschema5表示履歴に任意のcondition_weightingを追加する。profile_idはsource-order-linear-v1、positionsは条件IDと正規化原文開始位置（0〜2000）の組、最大64件でIDを重複させない。新規ConditionTextScore/BilingualConditionScoreへ整数weight（1〜64）を保存する。各条件のscore/score_ja/score_enは元の一致点を保持する。

旧plan/履歴/条件は追加fieldを省略し、既存JSON/digestを保持する。新規の履歴ranking_profile_sha256には集約metadataを結合し、単条件の点が旧方式と同じでも区別する。SQLite table/user_versionは変更しない。履歴のweightは保存位置と分類から検証し、本文の再取得・翻訳・再採点はしない。日本語のみの旧表示契約では条件内訳の追加保存を行わず、位置metadataと順位を保持する。

## 文章対画像の独立保存（EXEC-162）

schema5のranking_profile_idへcandidate-siglip2-dual-v2、provisional_profile_idへcounterfactual-siglip2-dual-v2、sort_profile_idへexcluded-title-conditions-text-image-review-v2を追加する。3値は同時に一致しなければならない。新規profileの商品は任意field visual_textを必須とし、商品hash・商品画像pixel hash（欠損時null）・最大3件の条件ID/文章hash/0〜1点・条件別最小値scoreを保存する。画像欠損では空条件とnull点だけを許容する。既存image_scoreは画像同士の点として別に保持する。

既存のpayload/digest/transaction/期限/owner境界を利用し、SQL schema移行は不要。旧profileにvisual_textを追加したり、旧履歴を再計算・並べ替えたりしない。旧fieldなしJSONのserialize結果も維持する。新profileの欠落fieldや旧profileに新fieldが混在する履歴は拒否する。現在結果と履歴のAPIはscores.textImage（文章対画像）とscores.image（画像同士）を別に返す。


## 画像なし準備の識別（EXEC-155）

CandidatePlanへ任意image_preparation=text-only-v1を追加する。未設定の旧計画ではJSONから省略してdigestを保持する。設定時は視覚Bonsaiのrequest/response hashとfocus/contrastの混在を拒否し、ローカルで保持した原文条件を日英テキスト採点にだけ使用する。画像ありへ進むには新しい準備が必要。既存のimage_mode=offの履歴契約・SQLite schema5・期限/削除を維持し、保存済み結果を再解釈/再採点しない。


## 対比指示の出典（EXEC-153/154）

準備計画のVisualCondition.contrastは任意fieldを維持し、v2/v3ではoriginとevidence（target、辞書由来の場合はdictionary_sha256・sense_ids）を保持する。対象原文の解釈と出典を条件/計画/画像要求digestへ束縛する。v3のgrammar出典はWordNetの語義IDに加えて既存JMdictのIDを許容し、辞書digestと束縛する。英名のBonsai補完はbonsai出典として辞書IDを付けない。v1ではevidenceを省略し、v1/v2の既存JSONを同じ形で読む。SQLite user_versionと保存済み履歴は変更せず、辞書変更による再採点や再生成を行わない。

## 検索対象の商品名（EXEC-150）

schema5のdetail_json metadataに任意の `product_name`（1〜100文字）を保存する。制御文字や不正な表示文字列は拒否する。値がない旧payloadではfieldを省略し、旧JSON/hashを維持する。candidateの画像あり/なしは準備済みの `title_comparison.product_name_ja` を渡す。新payloadのcompletion keyには `history_product_name` を含め、従来のpayloadと区別する。採点profile、SQLite user_version、既存レコードは変更しない。

一覧と詳細のAPIへ任意 `productName` を投影し、元の `summary` と `history_content.source_text` は保持する。旧レコードを補完保存・再採点しない。新fieldを含むJSONを読むには対応版が必要。稼働中の旧serverは静的画面の旧API互換で一覧表示を変更し、保存/API側の新fieldは次回通常起動以降に利用する。


## 接続画面の保存内容（EXEC-144）

schema5のdetail_jsonに任意history_content（profile=history-content-v1、source_text最大2000文字、condition_labels最大32件、condition_review最大24件）を追加する。原文範囲とquoteを検証し、採点済み条件IDには名称を要求する。商品行の任意thumbnail_pngはdata URLのRGB PNG、最大192×192・128KiB/枚・180000文字以内。48商品という既存読込上限を維持し、現行検索は24商品。任意値なしはJSON fieldを省略するため旧JSON/旧hashを変更しない。

新contentのcompletion keyをdomain分離し、全文/ラベル/画像をpayloadとdetailのdigestへ含める。入力/条件/商品PNGは同じdetail_jsonに格納するため、一つのtransactionで保存/rollback/削除される。既存生成画像は専有BLOB行とFK cascadeで連動する。元画像のURL再取得や旧履歴のbackfill/再採点は行わない。保持期間は完了から30日で、永続とはprocess再起動後の再表示を意味する。

## 履歴削除と期限削除の実行境界（EXEC-143）

既存のschema5 DELETEとforeign key cascadeをAPI/定期処理へ接続する。個別削除はowner+locator、期限削除はowner+expires_at<=server_nowで限定し、履歴行・detail JSON・専有PNG BLOBを同一transactionで削除する。secure_delete=ONで削除pageを処理するが、外部バックアップやfilesystemの残存領域の消去を保証するものではない。DB fileやschema、無関係な行、raw cacheは保持する。

BrowserHistoryはGETだけmode=ro、削除だけ既存file限定mode=rwを使う。未作成file/旧schemaは作成・移行しない。purge_expiredのowner_id追加はoptionalで従来caller互換を保つが、browser経路は必ずlocal-userを指定する。複数DBの削除はDBごとにatomicで、失敗を返した場合は冪等に再試行できる。期限到達後は削除前でも読込不可、定期処理はserver稼働中60秒間隔。旧点数/画像方式の再採点は行わない。


## 画像なし結果の保存（EXEC-142）

SQLite schema5/table/user_versionを変更せず、JSON契約にcandidate-image-free-v1とimage-free-v1を追加する。この対に限りimage_mode=off、reference_images=0件、condition_set_sha256/reference_set_sha256/runtime_sha256=null、image_weightなし、商品image_component_status=not_used/image_score=nullを要求する。画像ありprofileには従来の2〜4画像と画像hashを要求し、not_usedや空の商品集合を混ぜない。image_modeなしの旧serializerは追加fieldを省略する。

画像なし順位は否定>タイトル>優先>希望>レビューで、同点は取得順。total_scoreはタイトル点のみを記録し、画面では合成点として表示しない。ranking hashとcompletion keyを新profileへ結び付け、保存時のsource/order/scoreを再検証する。画像なしだけ商品0件を保存でき、一覧件数は0となる。旧行は移行・再採点しない。


## 条件解析の計画識別（EXEC-140）

新規CandidatePlanはoptionalな `condition_language_profile=condition-language-v1` と `condition_language_sha256` を対で持つ。digestは解析profileと正規化原文範囲/quote/照合target/strength/reasonを含む共通解析から作り、計画digestへ含める。構文提案がある場合はその条件fragmentを用いる。旧fieldなしのJSONは両fieldを省略して旧digestと旧解析を保持する。再実行時は保存された方式を選び、新方式では解析digestも再照合する。

neutralは共通解析と確認APIだけの分類で、採点用strengthはrequired/preferred/excludedの3値を維持する。確認APIのconditionReviewは原入力の文字位置とquote、照合target、strength、固定reason、conditionIssuesは位置/quote/固定codeを持つ。修正表示は元のUnicode文字列へ位置を戻す。本文をログ/diagnosticへ出力しない。SQLite schema5・既存行・保存結果の再採点/変換は変更しない。

EXEC-139の新規candidate最終ranking/schema5履歴はsort_profile_id=excluded-title-conditions-image-review-v1。否定条件の負方向、タイトル、優先、希望、画像、レビュー、取得順で検証し、旧title-image-conditions-v1を別の復元契約として保持する。商品へreview_rating（0〜5/null）を追加し、nullではJSON fieldを省略して旧digestを維持する。新規profileの保存時だけ取得済みratingを投影し、旧profileの再保存に新値を混ぜない。SQL table/user_version/旧行は変更しない。

EXEC-138の履歴閲覧は既存schema5をread-onlyで開き、schema変更やデータ移行をしない。owner/local-user、30日の失効条件と保存digestを既存repositoryで検証する。表示APIへ要約・日時・件数・商品/採点・生成画像を投影し、未保存の元入力全文/個別条件名/商品サムネイルを追加生成しない。読み取りでは期限切れを一覧/詳細から除外する。物理削除は後続のEXEC-143で接続した。

EXEC-137の接続APIは表示用PNGサムネイルと画像点・参考合成点を追加する。点数は既存の保存fieldから投影し、商品サムネイルは評価済み画像からprocess内で作る。商品画像をDBへ追加保存せず、SQLite schemaと旧履歴は変更しない。

## 日英条件採点と英語詳細の保存（EXEC-133）

新規CandidatePlanの任意 `condition_terms` はcondition-terms-v1、source/dictionary/translator/sense-model SHA256と条件ID・強さ・原文/英訳・同義語・語義ID・visual区分を保持する。最大64条件、各言語最大32語句。元の条件との対応とsource hashを検証し、plan digestに含める。価格は共通の観測値を使うため展開語句なし。

新規CandidateRankingはcandidate-confirmed-lexical-v5、text_scoreはcandidate-text-bilingual-v2と専用digest。title_scoresにscore_ja/score_en/最大score、条件行に同じ3点とselected_languageを保存する。英語未取得はnull。同点はjaを選択し、sourceはevidence/description/missingにproduct_textを加える。復元時に語句bundleと元の条件、商品観測値から日英点・最大値・順序を再検証する。画像完成結果も新text profile/digestを引き継ぐ。schema5表示履歴と接続APIに日英の数値内訳を投影するが、本文抜粋は複製しない。旧fieldなしのplan/result/historyは追加nullを出力せず旧方式で復元し、既存SQLiteの列・user_version・行を変更しない。

NormalizedProductCandidateに任意details_enとdetails_en_status（available/unavailable）を追加する。details_enはdescription最大4000文字、features最大20件/各200文字、color/material最大200文字。切り詰めをtruncated_fieldsで識別する。availableとdetailsの存在を対応させ、英語タイトルの欠損とは別に扱う。新要求のenglish_details=trueはenglish_titles=trueを必須とし、要求digestに含める。旧要求は両flagの省略状態を維持する。

CLI raw keyは取得版3と英語詳細flagを含め、raw/normalized/scoredをplaywright-v3へ分離する。CLIの正規化結果にも英語説明・特徴・詳細状態を保持するが、旧CLIの採点式は変更しない。旧playwright-v1/v2とOutscraper cacheの自動読替え・削除・変換はしない。

## 商品の英語タイトル保存（EXEC-131）

正規化商品とschema5表示履歴に任意field `title_en`（最大500文字）・`title_en_status`（available/unavailable）を加える。availableなら非空タイトルが必須、unavailableならnullとし、不整合をstrict復元時に拒否する。旧fieldなしのJSONは再出力でも両fieldを省略し、既存digestを保持する。主title、SQLite table/user_version、旧保存結果を変更しない。

新規Playwright要求の `english_titles=true` を要求digestへ結び付け、旧fieldなしの要求と分離する。旧要求の再構築は省略状態を維持する。CLI raw keyには取得版2と英語取得flagを加え、raw/normalized/scoredをplaywright-v2 namespaceへ保存する。旧playwright-v1とOutscraper cacheの自動読替え・変換・削除は行わない。CLI商品/採点結果も任意英語fieldを保持する。

## タイトル・画像優先の順位識別（EXEC-129）

EXEC-129時点のcandidate最終rankingとschema5表示履歴へ `sort_profile_id=title-image-conditions-v1` を追加した。以下は旧方式の保存/復元契約で、新規実行はEXEC-139を使う。タイトル、画像、否定条件、優先条件、希望条件、取得順で順序を検証し、既存の画像/text/係数digestにsort_profile_idを結合する。この方式はimage_weight=0.5を要求するが、合成点は順位keyに使わない。

fieldなし/nullの旧結果は従来の条件優先として読み、JSON再出力からfieldを省略する。直前の50:50方式も、その前の80:20方式も旧順位/点数/digestを保持する。SQLite table/user_versionや既存行を変更しない。画像評価前のCandidateRankingの旧内部順序はそのまま検証する。

## タイトル・画像の等重み合成（EXEC-128）

新規candidateの最終ranking、各商品row、schema5履歴のmetadataに `image_weight=0.5` を記録する。タイトルと画像の合成は各50%、画像不明時はタイトル点だけとする。親rankingと商品rowの係数が不一致なら拒否し、合成点も再計算して検証する。新しいranking_profile_sha256は既存画像/text digestにimage_weightを結合するため、同じ画像モデルでも旧80:20とcompletion keyを共有しない。

fieldなし/nullは旧candidateの80:20として読み、JSON再出力ではfieldを省略して旧digestを保持する。SQLiteのtable/user_versionは変更せず、旧行を更新・削除・再採点しない。旧semantic/typedの別採点方式へこのfieldを設定することは拒否する。現行式は [BACKEND.md](BACKEND.md#candidateの説明文タイトル採点exec-125) を参照。

## Playwright取得元と旧cacheの互換（EXEC-126）

新規CandidatePlanのrequestはprovider=playwright/schema1.0で、旧Outscraper2.0/2.1とのunionとして読む。要求digestは別domainで計算するため、同じ語句の旧要求や承認を新要求として使えない。保存済みplanから明示的に再実行する入口では、元bundle/approval receiptを検証した後にPlaywright要求を新規構築し、元計画と新計画の識別を保つ。

正規化batchと商品provenanceにproviderを加える。新規取得はplaywright、旧JSONの省略時はoutscraper。旧providerでは追加fieldを再serialize時にも省略して旧digestを保持する。既存の `outscraper_request_sha256` という保存field名は互換のため残すが、Playwright時の値は新providerの要求digestである。旧task adapterはplaywright接頭辞の実行IDで取得元を識別する。batch内の取得元不一致は拒否する。

SQLiteの列/schemaは変更せず、旧表示履歴や点数を更新しない。新規candidateの表示履歴JSONには `retrieval_provider=playwright` を保存し、read-backで保持する。旧履歴ではこのfieldを省略する。EXEC-126時点のCLIはraw/normalized/scoredを `playwright-v1/` namespaceへ保存し、raw keyにもprovider/取得版/日本語/配送先既定/上限を含める。旧outscraper cacheはそのまま保持し、自動読替え・変換・削除を行わない。

## candidateの説明文タイトル比較の保存（EXEC-125）

以下はEXEC-125で導入したv4保存の契約であり、EXEC-133の条件展開あり構成では上節のv5・言語別点数を追加する。

新規CandidatePlanの `title_comparison` に採点profile/digest、元語の日英商品表現、日英カテゴリ、明示ブランド/型番、最大3件の同義語対を固定し、plan digestと既存承認に結び付ける。未取得項目はnull。旧planはこのfieldを省略し、再保存時も不要なnullを加えず旧digestを保持する。

新規CandidateRankingは `candidate-confirmed-lexical-v4`。各商品に `text_score` を持ち、`candidate-text-v1` と固定digest、required_ratio/preferred_ratio/excluded_ratio、条件ごとのID・強さ・source・0〜1の一致度を記録する。sourceは既存観測を使ったevidence、説明文を使ったdescription、欠損missing。条件本文や一致した説明文の抜粋はこの内訳へ複製しない。復元時は商品・条件から点数と順序を再検証し、v4と旧plan/旧点数の混在を拒否する。

最終画像結果とschema5表示履歴には `text_profile_id=candidate-text-v1` を追加する。画像方式の既存ranking_profile_id/runtimeは維持し、ranking_profile_sha256は既存画像ranking digestと新text digestを合成して旧採点から分離する。SQLiteの列・user_versionは変更せず、payload JSONにtext_profile_idだけを追加する。表示履歴には条件スコア内訳やtitle_comparisonを複製しない。旧履歴はfieldなし・旧点数・旧digestで読み、既存行を更新・再採点しない。

計算式と抽出範囲は [BACKEND.md](BACKEND.md#candidateの説明文タイトル採点exec-125)、検証結果は [EXEC-125](GOAL.md#exec-125-説明文の条件一致とタイトル比較の拡張) を参照する。

## 1. 現在の永続化方式

現行の `run_product_search()` はRDBを採用せず、処理途中と最終結果をローカルファイルシステム上のJSONキャッシュへ保存する。次期検索には、これとは分離したPython標準SQLiteのローカル単一fileとして、履歴用schema version 2とjob metadata用schema version 1がある。データベースサーバー、ORM、運用migrationはない。履歴は次期offline検索結果の保存境界へ接続済み、jobは注入callback用executorへ接続済みだが、どちらもlegacy現行pipelineからは未参照である。

legacy cacheの「論理スキーマ」は、`src/schemas.py` のPydanticモデルとJSONファイルの配置規約を指す。次期検索履歴の正は `src/search_v2/history_repository.py`、local job metadataの正は `src/search_v2/search_job.py` のstrict modelとSQLite DDLである。アーキテクチャと処理の詳細は [BACKEND.md](BACKEND.md#統合済み全体設計)、保存上の制約は [REQUIREMENTS.md](REQUIREMENTS.md#統合済み制約)を参照する。

## 2. データフロー

```text
user_input: str
  -> Bonsai response content: str
  -> ProductAttributes
  -> Outscraper raw response: JSON object
  -> list[NormalizedAmazonProduct]
  -> list[ProductScore]
```

Pydanticモデルの正は `src/schemas.py` である。JSONから再利用する際は、属性、正規化商品、採点商品を対応するモデルで再検証する。

次期検索フローのdomain modelは `src/search_v2/intent.py` と `query_planner.py`、network非依存のBonsai応答境界は `bonsai_adapter.py`、意味語句の再分割は `tokenizer.py`、承認・状態・利用量境界は `approval.py`、`state_machine.py`、`usage_ledger.py`、Cloudflare要求・HTTP・画像正規化境界は `cloudflare_request.py` と `cloudflare_http.py`、Outscraper純粋要求契約は `outscraper_contract.py`、認可・HTTP・task境界は `outscraper_request.py` と `outscraper_http.py`、商品応答境界は `product_normalization.py`、採点結果境界は `ranking.py` と `typed_ranking.py`、Outscraper完了結果から検索完了までの結合境界は `product_pipeline.py`、Bonsaiから完了までの段階別結合境界は `orchestrator.py` に分離している。これらの一時stage、利用量ledger、`ProductSearchPipelineResult` はcache・DBへ自動保存しない。`history_snapshot.py` が正常完了result、承認済みstage、元入力をtyped表示用 `SearchHistoryWrite` へ変換し、`history_repository.py` がSQLiteへ冪等保存する。`search_job.py` は検索payloadやcallbackを永続化せず、固定local ownerのbinding・状態・時刻・結果locatorだけを別SQLiteへ保存する。`production_search.py` は承認済み暫定検索をjobへ投入し、成功時だけschema 5.0履歴locatorを保存する。`production_api.py` はこの既存状態を読み書きするlocal HTTP projectionであり、新しいtableやmigrationを追加しない。legacy現行pipeline、最終承認controller、server起動構成、UIからの投入は未実装である。

## 3. ファイル配置

`CACHE_DIR` の既定値はリポジトリルートの `cache/` である。相対パスを設定した場合もプロジェクトルートを基準に絶対パスへ解決する。

```text
cache/
  product_attributes/
    <attributes_key>.json
  outscraper/
    raw/
      <raw_key>.json
    normalized/
      <normalized_key>.json
    scored/
      <scored_key>.json
```

| 論理コレクション | namespace | JSONルート | 内容 |
|---|---|---|---|
| 属性 | `product_attributes` | object | `ProductAttributes.model_dump()` |
| 生レスポンス | `outscraper/raw` | object | Outscraperの成功レスポンス |
| 正規化商品 | `outscraper/normalized` | array | `NormalizedAmazonProduct.model_dump()` の配列 |
| 採点商品 | `outscraper/scored` | array | `ProductScore.model_dump()` の配列 |

`cache/` は `.gitignore` 対象である。ここは永続的な業務データベースではなく、再計算可能なアプリケーション生成物の置場である。

## 4. `ProductAttributes`

自然文から抽出・補正した検索条件を表す。

| フィールド | JSON型 | 必須 | 既定値・意味 |
|---|---|---:|---|
| `estimated_product_name_ja` | string | はい | 推定した日本語商品名 |
| `estimated_product_name_en` | string / null | いいえ | 英語商品名 |
| `category_ja` | string / null | いいえ | 根拠のある日本語カテゴリ |
| `category_en` | string / null | いいえ | 根拠のある英語カテゴリ |
| `color_ja` | string / null | いいえ | 日本語の色 |
| `color_en` | string / null | いいえ | 英語の色 |
| `features_ja` | array[string] | いいえ | 空配列。日本語の特徴 |
| `features_en` | array[string] | いいえ | 空配列。英語の特徴 |
| `negative_conditions_ja` | array[string] | いいえ | 空配列。日本語の除外条件 |
| `negative_conditions_en` | array[string] | いいえ | 空配列。英語の除外条件 |
| `search_queries_ja` | array[string] | いいえ | 空配列。Outscraper候補の日本語検索語 |
| `search_queries_en` | array[string] | いいえ | 空配列。英語検索語 |
| `required_terms_ja` | array[string] | いいえ | 空配列。日本語の必須語 |
| `required_terms_en` | array[string] | いいえ | 空配列。英語の必須語 |
| `preferred_terms_ja` | array[string] | いいえ | 空配列。日本語の優先語 |
| `preferred_terms_en` | array[string] | いいえ | 空配列。英語の優先語 |
| `related_terms_ja` | array[string] | いいえ | 空配列。日本語の関連語 |
| `related_terms_en` | array[string] | いいえ | 空配列。英語の関連語 |
| `price_preference` | string / null | いいえ | `cheap`、`premium`、`none` をプロンプトで要求 |
| `min_price_jpy` | integer / null | いいえ | 明示された下限 |
| `max_price_jpy` | integer / null | いいえ | 明示された上限 |
| `target_price_jpy` | integer / null | いいえ | 明示された目標価格 |
| `expected_price_min_jpy` | integer / null | いいえ | 推定相場の下限 |
| `expected_price_max_jpy` | integer / null | いいえ | 推定相場の上限 |

### 4.1 保存前の補正

- リスト項目の `null` は空配列、文字列は1要素配列にする
- 価格は正の整数だけを残す
- 通貨記号、`JPY`、桁区切りを含む整数表現を受け付ける
- 0、負数、非整数、非有限値、不明な型は `null` にする
- 明示価格帯と推定相場の上下限が逆なら入れ替える
- 根拠の薄いカテゴリを `null` にする
- 検索語を商品名、色、特徴、根拠のあるカテゴリから再構成する

### 4.2 モデル上の注意

`price_preference` の列挙値や各配列の最大件数はPydanticモデル自体では制約していない。価格補正と範囲整合は属性抽出サービスで行うため、別経路で `ProductAttributes` を直接生成すると同じ保証は得られない。

### 4.3 次期intentとquery plan（未永続化）

`SearchIntentDraft`、`NormalizedSearchIntent`、`SearchQueryPlan` は全field required、任意値は明示的な `null`、`strict=True`、`extra="forbid"` を使う。価格mode、各field・配列上限、intent全体49,152 UTF-8 bytes、nested instance再検証、provenance digest、query言語・件数・長さをmodelで検査する。response adapterはsource input、exact prompt、canonical draft schema、full raw response bodyのdigestを付け、tokenizerを通したquery文字列はplan digestへ反映されるが、本文やdigestを現行cacheへ保存しない。これは現行 `ProductAttributes` のcache互換schemaを置き換えず、保存namespace、TTL、migrationは後続Planで決定する。

### 4.4 次期承認stateと利用量ledger（未永続化）

schema 3.0の `SearchApprovalPlan` はowner、session、intent・query、readyなtyped proposal digest、Outscraper request digest、任意画像set、provider allowance、固定 `typed-ranking-v4`・product evidence profileを含むruntime binding、作成時刻・15分期限を固定する。schema 3.0の `SearchSessionSnapshot` は `draft` から商品受信・正規化・検索完了または固定失敗までの段階、revision、intent・queryと同時に保持するtyped proposal digest・readyまたはblocking status、画像set試行、activeまたはfailed画像reservation ID、承認tokenのSHA-256、後半の件数・typed batch digest・正常結果種別または失敗工程・固定コードを保持する。blocking状態は `intent_review` から先へ進めない。`image_generation_failed` ではactive IDと画像digestを持たず、直近のfailed IDだけを持つ。raw approval token、provider response、query本文、商品本文、URL、生例外文はsnapshotへ保存しない。旧2.0 plan・snapshotとranking-v3 runtimeを新schemaとして読み替えない。

先行画像の確認には別のschema 1.0 `ReferenceReview` を使う。`reference_review` または `reference_generation_failed`、元のready intent、条件set、先行requestと任意の1枚artifact、先行最大2件と過去後続の利用量、policy digest、完了から15分の期限を保持する。元入力全文は保存しない。任意の `failure_diagnostic` は固定stageと、HTTP失敗時だけの整数statusをstrict modelで保持し、成功reviewには付けない。provider本文や例外を保存せず、診断追加前の未消費reviewを新承認へ暗黙移行しない。現在の承認待ちと消費状態はledger別のprocess-local registryへ保持し、DBへ永続化しない。schema 3.0 `SearchApprovalPlan` のoptional `reference_generation_sha256` は先行確認、条件、後続偽画像、過去後続利用量を追加で固定し、旧4方向だけの承認と区別する。

新 `ImageReview` schema 4.0は旧4方向 `execution` をNoneに限定し、`ReferenceReview` と `CounterfactualCloudflareDerivedExecution`、状態・request・reference・usage bindingを必須にする。`SearchApprovalPlan.image_generation_profile=reference_counterfactual` と先行計画のflow markerで旧経路のdigestを分離する。旧未消費承認は移行せず再確認から作り直す。

`UsageLedgerSnapshot` はprovider policyとreservationを、`ApprovalConsumptionSnapshot` は消費済みtoken digestを表す。利用量はcall、token、整数micro-USDで保持し、予約時刻はledger側のUTC時刻を使う。現在の `InMemoryUsageLedger` と `InMemoryApprovalLedger` は同一process内だけをlockし、snapshotからの再構築はできるが、ファイル、cache、RDBへ自動保存しない。複数process・host、再起動をまたぐ原子性、CAS、transaction、migration、retentionは後続repositoryで決定する。

### 4.5 Cloudflare request metadata（未永続化）

`CloudflareImageRequest` はintent・preimage plan・prompt contractのdigest、model、angle、attempt、prompt、512px寸法、seed、任意の参照PNG metadataを持つ。`CloudflareRequestSet` は基準、左、右、背面の固定4件と同じattemptを結ぶ。派生3件の参照PNG metadataはSHA-256、byte長、縦横を持つが、multipartへ渡す画像bodyはPydanticのserializable dumpから除外する。request・setのdomain-separated digestはこのmetadataを固定する。

`CloudflareImageArtifact` は角度、attempt、request SHA-256、`image/png`、正規化PNGのSHA-256・byte長・512×512寸法を持つ。PNG bodyは同一process内の後続処理用fieldであり、Pydanticのserializable dumpとreprから除外する。`CloudflareImageSetExecution` は固定順の4 artifact、image set・request metadataのSHA-256、成功済み4-call利用量予約、`image_review` sessionを結び、request・artifact・reservation・sessionのbindingを構築時に再検証する。

互換・診断用に残す旧4方向の `CloudflareImageRequest` と `CloudflareRequestSet` のschema 3.0では、正面を含む4要求すべてが同じ了承済み511px参照PNGを持つ。先頭に参照を持たない旧schema 2.0の低位adapterと区別し、旧requestを新しい先行了承の証拠として読み替えない。画像bodyのserializable dump・repr除外と既存4方向履歴の保存形式は維持する。

これらは外部送信前後の一時contractであり、現行cache、承認snapshot、RDBへ自動保存しない。mock・合成JPEG・PNG・WebPによるexecutionとRGB PNG正規化は実Cloudflareの送信記録または生成物保存記録ではない。将来request metadataまたは生成画像を監査・履歴保存するときも、画像body、account ID、Authorization、API tokenを同じrecordへ入れず、provider request IDの有無、出力SHA-256、所有者、保持期限、物理削除との関係を別Planで定義する。

### 4.6 Outscraper request metadata（未永続化）

`OutscraperAmazonProductsRequest` はGET endpoint、query plan SHA-256、日英最大2件のquery、`amazon.co.jp`、`ja`、server-side postal code、24件/query、`async=true`、最大候補数24または48件を固定する。`query_parameters()` は同名 `query` を計画順に反復し、それ以外を `domain`、`language`、`postal_code`、`limit`、`async` のallowlist順で返す。domain-separated request digestにはendpointと全fieldを含めるが、API key、header、raw approval tokenはmodelに存在しない。

`AuthorizedOutscraperRequest` はrequest、`scrape_submitted` snapshot、approval plan SHA-256、usage reservation ID、承認時刻を一時的に結ぶ。raw tokenとcredentialは持たず、現行cache、RDB、履歴へ保存しない。これは同一process内のoffline execution permitであり、HTTP送信、provider request ID、結果取得、複数process間の原子的claimを示すrecordではない。

`OutscraperProductExecution` は検証済みrequest、provider request ID、完了済みの限定 `data`、poll回数、`succeeded` の利用量予約を一時的に結ぶ。API key、結果URL、任意header、Requests object、失敗時の生応答は持たず、現行cache、RDB、履歴へ自動保存しない。Requests通信をmockした境界ではtask作成・結果取得・利用量確定まで確認済みだが、実providerの送信実績または永続監査recordではない。offline後半pipelineはこのobjectを一時入力として再検証する。raw productは履歴repositoryへ保存せず、正常完了した後半resultだけを `history_snapshot.py` が表示用snapshotへ変換する。

### 4.7 次期正規化商品batch（未永続化）

`ProductNormalizationProfile` はschema version、`observed-only-v2` profile ID、明示的なUSD/JPY換算率を固定し、そのcanonical digestを結果へ残す。`NormalizedProductBatch` はOutscraper request・query planのdigest、provider request ID、最大候補数、正規化商品、固定理由のrejectを持ち、batch全体にもdomain-separated SHA-256を計算できる。

`NormalizedProductCandidate` はASIN、title、store、description、価格・元通貨、rating、符号付き64-bit以下のreview count、Prime、在庫・配送、Amazon HTTPS商品URL、HTTPS画像URL、切詰め・破棄fieldとprovenanceを持つ。切詰め・破棄field名も列挙値へ限定する。`ObservedProductAttributes` のbrand、categories、color、material、featuresはproviderの構造化fieldだけから作り、欠損値を `unknown` に列挙する。titleやdescriptionから属性を推論せず、Prime欠損も `false` ではなく `null` のままにする。

provenanceはrequest・query plan digest、provider request ID、query index・language、response indexを持つが、query本文、postal code、credential、raw approval token、raw responseはbatchへ複製しない。このnormalizer単独は検証済みrequest descriptorへ応答を結ぶだけで、`AuthorizedOutscraperRequest` の消費、HTTP送信またはprovider成功を証明しない。offline後半pipelineは成功済みexecutionとの結合を再検証する。現行 `outscraper/normalized` namespaceと `NormalizedAmazonProduct` は変更しない。次期履歴repositoryもこの内部batchを直接保存せず、後続の表示用snapshot変換だけを受ける。

### 4.8 次期ranking batch（未永続化）

`RankingProfile` はschema `3.0`、profile ID `ranking-v3`、title 0.35、attributes 0.30、price 0.20、image 0.10、review quality 0.05、required term 3、preferred term 2、その他属性term 1、negative 1件0.20・最大0.50、高評価閾値4.0、最大rating 5.0、review count飽和1,000件、画像採点無効、小数4桁をstrict・frozenな固定値として持つ。canonical JSONとv3 domain separatorからprofile SHA-256を計算するため、weightやレビュー式だけを差し替えた同一profileとして扱えない。

`ScoreComponent` は `status`（`available`、`missing`、`disabled`）、固定理由、0〜1のscoreまたは `null`、base weight、欠損を除外して再正規化したeffective weight、4桁のcontributionを持つ。`ScoreBreakdown` はtitle・attributes・price・image・review qualityの5component、利用可能なbase weight、減点前score、negative penalty、総合score、採用した日英言語、一致・不足・negative termを持つ。review qualityは平均4.0以上である場合だけ `rating / 5.0` と、`min(1, log1p(review_count) / log1p(1000))` の積を採用する。ratingまたはreview countの片方が欠ける場合はmissingとし、画像componentは実CLIP推論と品質評価が完了するまで `disabled` に固定する。将来の画像componentも色、外観形状、商品種別など視覚的特徴だけの補助評価とし、有線・無線を含む構造化属性の推定、補完、上書きを行わない。有線・無線はtitle・attributes componentで判定する。

`RankedProduct` は1始まりのrank、元の `NormalizedProductCandidate`、`ScoreBreakdown` を結ぶ。`RankedProductBatch` はranking profile、intent、query plan、normalized product batchの各SHA-256と、最大48件のranked productを持つ。順位は総合score降順、同点は正規化時の全候補で一意な `response_index` 昇順であり、ranked batch全体もdomain-separated SHA-256へ結ぶ。

独立した `TypedRankingProfile` はschema `4.0`、profile ID `typed-ranking-v4`、v3 source profile digest、固定分母のtyped score version、必須状態を先に扱うsort key versionを持つ。base weightはtitle 0.35、typed attributes 0.30、price 0.20、image 0.10、review quality 0.05で、imageは無効、review qualityは唯一の最小weightである。`TypedScoreBreakdown` は自由語attributesの言語・一致語・不足語を持たず、条件数、満足weight、全条件weightとtyped attributes componentを保持する。required・preferredの `match` とexcludedの `mismatch` だけを満足weightへ加え、`unknown`・`conflict` も全条件weightに残す。条件0件ではtyped attributesを `missing/not_requested` とする。

`TypedRankedProduct` は正規化商品、再生成可能な `ProductEvidenceSet`、`TypedProductEvaluation`、v4 breakdownを結ぶ。`TypedRankedProductBatch` はv4 profile、v3 source ranking batch、intent、query plan、normalized product batch、typed proposal、registry、requirement set、product evidence profileの各SHA-256と最大48件の商品を持つ。schema、profile、batch hash domainをv3から分け、旧batchをv4として検証できない。順位は必須状態、required一致率、preferred一致率、v4総合score、response indexの順である。

これらは内部domain modelであり、現行 `outscraper/scored` cache、`ProductScore`、CLIへ直接保存しない。schema 3.0の `product_pipeline.py`、orchestration、stateはready proposalと `typed-ranking-v4` だけを扱い、typed batch digestを完了stateへ記録する。schema 2.0の `history_snapshot.py` はprovider metadata、digest、raw score、effective weight、内部証拠を除き、必須状態とdecisionを一致・未確認・情報矛盾・不一致等の利用者向けallowlistへ変換する。旧v3 batch、旧検索schema、SQLite version 1を暗黙変換しない。browserへ返すAPIは未実装である。

### 4.9 次期検索後半pipeline result（履歴変換を一部実装）

schema 3.0の `ProductSearchPipelineResult` は `results`、`empty`、`failed` のoutcomeと `SearchSessionSnapshot` を結ぶ。正常時だけ `NormalizedProductBatch` と `TypedRankedProductBatch` を別fieldで返し、失敗時は両方を `null` にする。商品を含むbatchはreprへ露出させず、sessionへは候補・正規化・除外・ランキング件数、typed batch digest、正常結果種別または失敗工程・固定コードだけを投影する。

`results` と `empty` はいずれも正常完了であり、0件を例外または失敗履歴へ変換しない。`failed` はprovider実行、正規化、rankingの固定工程だけを示し、生provider応答、query、postal code、商品本文、URL、生例外文を結果stateへ持たない。現在は同一process内の一時resultである。`history_snapshot.py` は正常result、承認済み `SearchReview`、exact digestへ一致する元入力とtyped proposalからschema 2.0の表示用履歴を作り、失敗resultと結合不一致を保存前に拒否する。legacy現行pipelineからの保存呼出し、CAS、複数worker向けtransaction、運用migration、API接続は未実装である。

### 4.10 次期検索orchestration stage（未永続化）

schema 3.0の `IntentReview` はstrict intent、query plan、intentから固定registryで再構築できるtyped proposal、`intent_review` session、Bonsai request・利用量reservationの識別情報を結ぶ。blocking proposalはこのstageには保持するが後続操作を拒否する。`ImageReview` は同じready proposalにCloudflare request set、正規化済み4画像、最大2件の成功・失敗を含む画像attempt履歴を加え、直近attemptだけを成功済みexecutionへ結ぶ。`ImageFailureReview` は部分画像を持たず、同じproposal、固定 `image_generation_failed` code、同名session state、直近failed reservation、最大2件の画像attempt履歴を結ぶ。`SearchReview` は同じready proposal、画像採用または画像OFFを確定した `search_approval` session、Outscraper request、normalization・typed ranking・product evidence profile、provider allowance、runtime・利用policy digestを結ぶ。各stageは本文、credential、生provider応答、raw approval tokenを永続fieldに持たない。

`ApprovedSearch` は最終承認後のraw single-use tokenを同一process内で一時保持する非Pydantic dataclassであり、reprを無効にしている。tokenはstage、approval plan、session、利用量ledger、`ProductSearchPipelineResult`、cache、DBへ保存しない。`run_search()` はtoken再利用を新しいOutscraper reservationとtransport callより前に拒否する。

これらのstageと結果はrepository recordではなく、再起動後に復元できない。生成済み画像の破棄または失敗後の画像なし続行でも、Cloudflare reservationは利用量ledgerへ残し、最終 `SearchReview` だけを画像OFFとして扱う。途中失敗後の明示retryは新しい4-call reservationを使い、成功後の画像利用量には失敗分も含める。正常完了resultと最終 `SearchReview` から表示用履歴へ変換・保存するoffline境界は実装した。利用量との一体transaction、CAS、再起動可能なstage永続化、API接続は後続Planで定義する。

### 4.11 型付き条件と証拠model（最小domainを一部実装）

型付き条件は、現行 `NormalizedSearchIntent` の文字列配列へfieldを継ぎ足さず、独立したschema version `1.0` の一時domain modelとして導入した。論理modelの実装状態は次のとおりである。

| model | 状態 | 主なfield | 責務 |
|---|---|---|---|
| `AttributeDefinition` | 一時domain実装済み | category、attribute key、value type、operator・unit・source allowlist、evaluator ID・version、default weight | repository内のtrusted registry entry。LLMや商品データから構築しない |
| `BonsaiTypedConditionCandidate` | intent応答へ実装済み | 非信頼attribute key、operator、JSON-native expected value、strength | Bonsaiが既存1回のstrict応答で提案する条件。evaluator・weight・registry指定を持たない |
| `TypedIntentAdapterProfile` | 一時domain実装済み | profile・decimal parser・requirement ID version、最大候補数 | Bonsai候補をlocal registryへ渡す固定変換profileを表す |
| `TypedRequirement` | 一時domain実装済み | requirement ID、attribute key、operator、typed expected value、strength、registry SHA-256 | 利用者が確認する1条件を表す |
| `TypedConditionIssue` | 一時domain実装済み | candidate index、固定code、blocking | unknown key、registry不整合、semantic hard条件、重複、上流ambiguityを本文なしで表す |
| `TypedRequirementProposal` | offline経路接続済み | ready・blocking、intent・candidate・registry・requirement・profile SHA-256、partial requirement、issue | Bonsai候補をtrusted条件または確認待ちへ分け、第1確認から履歴まで同じdigestで結ぶ |
| `ProductEvidenceAdapterProfile` | 一時domain実装済み | schema・profile ID、structured・title parser version、1 sourceの最大一致数 | 正規化済み商品から証拠を作る固定parser profileを表す |
| `EvidenceObservation` | 一時domain実装済み | requirement・product ID、source、typed observed valueまたはunknown reason、profile・input・evaluator digest | 商品情報または画像から得た1件の有界な観測を表す |
| `ProductEvidenceSet` | offline後半接続済み | product・registry・requirement set・profile SHA-256、requirement ID、証拠tuple | 1商品について作った正規順の証拠一式を結ぶ。商品本文は保持しない |
| `RequirementDecision` | 一時domain実装済み | `match`・`mismatch`・`unknown`・`conflict`、採用・不採用evidence digest、固定reason | attributeごとの優先規則で証拠を裁定した結果を表す |
| `ImageComparisonResult` | 未実装 | reference set、候補pixel、CLIP runtime digest、4方向score、平均、image score | 外観参照と候補画像の連続scoreを表す。exact属性の証拠にはしない |
| `TypedProductEvaluation` | offline後半接続済み | 必須状態、必須・希望condition score、coverage、decision一覧、条件set binding | 条件判定を候補非依存の順位keyと表示理由へ結ぶ |
| `TypedRankingProfile` | offline経路接続済み | v4・v3 source profile、typed score・sort key version、固定weight、画像無効 | v3と分離した型付きranking規則を承認runtimeへ固定する |
| `TypedScoreBreakdown` | offline後半接続済み | title・typed attributes・price・image・review、条件数・満足weight・固定分母、negative penalty | 自由語attributesを持ち込まず、未知条件を分母へ残した総合scoreを説明する |
| `TypedRankedProduct` | offline後半接続済み | 正規化商品、限定証拠、全条件評価、v4 score breakdown | 1商品の証拠・判定・採点をproduct digestへ結ぶ |
| `TypedRankedProductBatch` | offline後半接続済み | v4 profile、v3 source、intent・query・商品batch・proposal・registry・evidence profile digest、順位 | 必須状態を先に扱う最大48件のranking-v4結果を表す |

`expected_value` と `observed_value` は値型ごとのdiscriminated unionにし、文字列1 fieldへboolean、数、range、setを混在させない。数値にはregistryで許可した単位を必須にし、単位変換profileもdigestへ含める。`unknown` は値を持たず、`mismatch` の代替として使わない。`conflict` は矛盾した元値を通常画面へそのまま返さず、source IDと固定reasonを内部証拠へ保持する。

条件一致率は検索で要求されたweight合計を分母へ固定し、商品ごとにunknownを除外して再正規化しない。この規則は独立 `typed-ranking-v4` のtyped attributes componentへ実装し、schema・profile・batch digestをv3から分けた。旧cacheや履歴は新schemaとして読み替えない。

実装済みmodelは同一processの一時値であり、現行JSON cacheを変更していない。既存Bonsai strict intentから条件proposalを作るadapter、`NormalizedProductCandidate` から限定した型付き証拠を作るadapter、ready proposalからv4順位を作る境界は、schema 3.0の第1確認、承認、state、pipelineへ接続済みである。schema 2.0の履歴は、内部のattribute key、evaluator、digest、raw score、evidenceを直接公開せず、条件ごとの「一致」「未確認」「情報が矛盾」「不一致」等に変換した表示allowlistと必須状態だけを保存する。legacy現行検索、JSON cache、API、UIへの接続は未実装である。

### 4.12 holdout評価artifact（永続repository未実装）

`holdout_evaluation.py` のschema 1.0は、正解、予測、reportを別model・別digestにする。いずれもfileやDBを自動的に読み書きせず、呼出元が与えたin-memory値だけを扱う。

| artifact | 主なfield | 保存しない内容 |
|---|---|---|
| `HoldoutGroundTruthDataset` | holdout role、dataset・provenance ID、case、category、query language、source input digest、canonical exact条件、商品digest、期待decision、関連度grade | 検索文、商品本文・ASIN・URL、画像、元Excel metadata |
| `HoldoutPredictionSet` | dataset・profile binding、case状態、intent・query・proposal・ranking digest、条件identity、商品digest、decision、必須状態、順位 | runtime model本体、検索文、商品本文・ASIN・URL、生provider応答、生例外 |
| `HoldoutEvaluationReport` | profile・dataset・prediction digest、case・category・全体の件数と比率、coverage issue、`quality_decision=not_assessed` | 正解条件本文、商品label本文、任意の合格閾値 |

予測builderだけが完全なruntime artifactを一時入力として再検証し、`digests-states-ranks-only-v1` へ投影する。将来永続化する場合も、この限定schemaを保存単位とし、正解labelのアクセス制御、holdout分割記録、保持期限、at-rest保護、blind評価を別Planで定義する。現行cacheとSQLite検索履歴には保存せず、schema migrationも発生しない。

### 4.13 holdout品質判定artifact（永続repository未実装）

`holdout_acceptance.py` のschema 1.0は、固定policyと1つの評価reportに対するassessmentを別model・別digestにする。自動的なfile・DB読書きは行わず、既存の評価reportも変更しない。

| artifact | 主なfield | 保存しない内容 |
|---|---|---|
| `HoldoutAcceptancePolicy` | policy・evaluation・ranking profile IDとdigest、metric桁数、全体・category判定規則、固定閾値 | dataset固有の値、検索文、商品情報、実評価結果 |
| `HoldoutAcceptanceAssessment` | policy・report・dataset・prediction・profile digest、`pass`・`fail`・`ineligible`、固定順check | 正解条件本文、商品本文・ASIN・URL、生provider応答、生error |
| `HoldoutAcceptanceCheck` | scope、category、metric、operator、観測値、基準値、成否 | query、商品識別本文、自由記述reason |

assessmentの永続化、blind評価、labelへのアクセス制御、署名、時刻証明は実装していない。digestは内容差し替え検出のbindingであって、holdoutが本当に未使用だったことや入力が匿名であることを証明しない。現行cacheとSQLite検索履歴には保存せず、schema migrationは発生しない。

## 5. Outscraper生レスポンス

生レスポンスはPydanticモデルで包まず、JSON objectのまま保存する。完了結果では `data` が配列であることをクライアント境界で検証する。

正規化で参照する主な外部フィールド:

```text
data
name, asin, store_title
price_parsed, price, old_price_parsed, strike_price_parsed
old_price, strike_price, delivery_price, currency
rating, reviews, categories, description
high_res_images, image_1 ... image_10
url, short_url, prime, availability, shipping
query, position
```

APIキーは生レスポンスpayloadへ追加しない。

## 6. `NormalizedAmazonProduct`

Outscraper商品1件を後段で扱う形式へそろえたモデルである。

| フィールド | JSON型 | 必須 | 既定値・意味 |
|---|---|---:|---|
| `source` | string | いいえ | `amazon` |
| `asin` | string / null | いいえ | 商品識別子 |
| `title` | string | はい | 商品名。空タイトルは保存前に除外 |
| `brand_or_store` | string / null | いいえ | ブランドまたはストア名 |
| `price_jpy` | integer / null | いいえ | JPYへ換算済みの価格 |
| `list_price_jpy` | integer / null | いいえ | JPYへ換算済みの旧価格等 |
| `currency` | string / null | いいえ | 検出した元通貨 `JPY` または `USD` |
| `rating` | number / null | いいえ | 評価 |
| `review_count` | integer / null | いいえ | レビュー件数 |
| `categories` | array[string] | いいえ | 空配列 |
| `image_url` | string / null | いいえ | 表示用の先頭画像 |
| `image_urls` | array[string] | いいえ | 空配列。重複除去済み画像 |
| `product_url` | string / null | いいえ | 商品URL |
| `short_url` | string / null | いいえ | 短縮URL |
| `is_prime` | boolean | いいえ | `false` |
| `availability` | string / null | いいえ | 在庫情報 |
| `shipping` | string / null | いいえ | 配送情報 |
| `source_query` | string / null | いいえ | 外部レスポンス内の検索語 |
| `position` | integer / null | いいえ | 元検索順位 |
| `description` | string / null | いいえ | 商品説明 |

### 6.1 正規化規則

- `data` の辞書と1段ネストした辞書配列を候補として取り出す
- 文字列の前後空白を除く
- 通貨が明示されていればJPY・USDだけを許可する
- USDは `USD_TO_JPY_RATE` を掛けて整数化する
- JPYは数値の小数部分を切り捨てる
- 負の価格は `null` にする
- Primeはbool、数値1、文字列 `1`、`true`、`yes`、`y` を真とする
- 高解像度画像、`image_1` から `image_10` の順に重複を除く
- ASIN、短縮URL、商品URL、タイトルの順で重複キーを選ぶ

URLスキーム、文字列長、評価範囲、レビュー件数の非負性は現行Pydanticモデルで制約していない。

## 7. `ProductScore`

UIとCLIへ返す採点済み商品の形式である。

| フィールド | JSON型 | 必須 | 意味 |
|---|---|---:|---|
| `asin` | string / null | いいえ | 商品識別子 |
| `title` | string | はい | 商品名 |
| `price_jpy` | integer / null | いいえ | 円換算価格 |
| `rating` | number / null | いいえ | 評価 |
| `review_count` | integer / null | いいえ | レビュー件数 |
| `image_url` | string / null | いいえ | 表示画像 |
| `product_url` | string / null | いいえ | 商品URL |
| `title_similarity` | number | はい | 商品名類似度 |
| `attribute_similarity` | number | はい | 属性TF-IDFまたは条件一致率 |
| `price_score` | number | はい | 価格条件への近さ |
| `negative_penalty` | number | はい | 除外条件による減点 |
| `total_score` | number | はい | 0.0以上1.0以下の総合値 |
| `matched_terms` | array[string] | いいえ | 採用言語で一致した条件 |
| `missing_terms` | array[string] | いいえ | 採用言語で不足した条件 |
| `negative_matches` | array[string] | いいえ | 一致した除外語 |

類似度とスコアは小数4桁へ丸める。保存順は `total_score` の降順である。

## 8. キャッシュキーの論理スキーマ

キー材料をキー名順のコンパクトJSONにし、SHA-256の16進表現の先頭24桁をファイル名にする。

### 8.1 属性キー

```text
type, version, cache_scope, user_input,
bonsai_base_url, bonsai_model, prompt_sha256,
temperature, max_tokens
```

入力は前後空白除去後の文字列を使う。プロンプト本文は保存せずSHA-256全体を材料にする。

### 8.2 生レスポンスキー

```text
type, cache_scope, query, endpoint,
domain, language, postal_code, limit
```

APIキーは含めない。

### 8.3 正規化キー

```text
type, version, cache_scope,
usd_to_jpy_rate, raw_response
```

生レスポンス全体を材料に含める。

### 8.4 採点キー

```text
type, version, attributes, normalized_cache_key,
title_score_weight, attribute_score_weight, price_score_weight,
required_term_weight, color_term_weight, feature_term_weight,
preferred_term_weight, related_term_weight
```

`normalized_cache_key` がscopeを含むため、採点もscopeごとに分かれる。

### 8.5 実装版

現行の属性、正規化、採点キャッシュ版はそれぞれ文字列 `"2"` である。変換結果が変わる非互換変更では該当版を更新し、旧ファイルをキャッシュミスにする。

## 9. scopeによる分離

- Python呼出元が異なるscopeを指定した場合、同じ入力でも異なるキーになる
- CLIとscope未指定のPython呼出は `local-cli` を継続利用する
- scopeは1文字以上128文字以下である

scopeは認証ユーザーID、秘密情報、アクセス制御境界ではない。すべてのファイルは同じ `CACHE_DIR` 配下に置かれる。

## 10. TTL

| コレクション | 設定 | 既定値 | 判定方法 |
|---|---|---:|---|
| 属性 | `LLM_CACHE_TTL_SECONDS` | 86400秒 | ファイルmtimeからの経過時間 |
| 生レスポンス | `OUTSCRAPER_CACHE_TTL_SECONDS` | 3600秒 | ファイルmtimeからの経過時間 |
| 正規化商品 | なし | 無期限 | キー一致とモデル検証 |
| 採点商品 | なし | 無期限 | キー一致とモデル検証 |

期限切れファイルはキャッシュミスになるが削除されない。`ENABLE_CACHE=false`、`use_cache=False`、`--no-cache` は読込を止めるだけで、保存は継続する。

## 11. 原子的書込

すべてのキャッシュ保存は `src/utilities/json_editor.py` の `write_json()` を通る。

1. 保存先ディレクトリを作成する。
2. 保存先と同じディレクトリに名前付き一時ファイルを作る。
3. UTF-8、インデント2、末尾改行付きでJSONを書く。
4. `flush()` と `os.fsync()` を実行する。
5. `Path.replace()` で目的ファイルへ置換する。
6. 失敗時に残った一時ファイルを削除する。

同一ファイルを読者が途中まで読む危険は減らせるが、複数プロセス間の相互排他ロックはない。

## 12. 読込と破損時の扱い

`JsonCacheRepository` は次をキャッシュミスとして返す。

- ファイルが存在しない
- TTLを超えている
- 読込時のOSエラー
- UTF-8デコードエラー
- JSON構文エラー

namespaceが絶対パスまたは `..` を含む場合は拒否する。キーは空でない小文字16進数だけを許可する。属性、正規化商品、採点商品はさらにPydantic検証を行い、不一致なら再計算する。破損ファイルの隔離、削除、通知は現時点で行わない。

## 13. 共通エンベロープを持たないこと

各JSONはpayloadそのものを保存し、次の共通メタデータを持たない。

- schema version
- created_at / expires_at
- cache scope
- キー材料
- producer version
- integrity checksum

版と設定はファイル名を決めるキー材料にだけ含まれる。作成時刻とTTLはファイルmtimeへ依存する。

## 14. 保存データと保護

キャッシュには利用者入力から抽出した条件、商品タイトル、説明、価格、評価、画像URL、商品URL、一致・不足・否定条件が保存され得る。APIキーはキャッシュキーとpayloadへ含めない。

- `cache/` をGitや公開Webルートへ含めない
- 共有ホストではOSのディレクトリ権限で保護する
- キャッシュ内容をログ、Issue、完了報告へ貼り付けない
- scopeを認証や秘密保持の代替にしない

詳細は [SECURITY.md](SECURITY.md)を参照する。

## 15. RDB等へ移行する判断条件（未実装）

次のいずれかが必要になった場合、ローカルJSON継続かRDB・オブジェクトストレージ移行かをExecution Planで決める。

- 複数ワーカーから同じデータを安全に更新する
- 利用者・テナント単位の認可を永続的に適用する
- 複数process・複数hostで検索ジョブの状態遷移、再開、監査履歴を保証する
- 容量上限、期限削除、検索、集計を運用要件にする
- 破損検知、バックアップ、復旧目標を保証する

`SearchJobStatus` はlocal単一process向けのjob metadataへ実装した。公開・複数利用者向けの `SearchResult`、運用用 `ExternalApiError`、共通 `CacheEnvelope` は現行入出力に存在しない。

## 16. 次期検索履歴の論理モデル（offline変換・SQLite repositoryを一部実装）

検索履歴は再計算用cacheとは別の永続データである。正常に完了した検索1回を1項目として保存し、cache TTLが切れても履歴一覧と保存済み結果を表示できるようにする。失敗・中止した検索は結果履歴へ保存せず、正常な0件は保存する。

### 16.1 `SearchHistoryEntry`

| field | 内容 |
|---|---|
| `history_id` | 推測困難なserver-side主キー。通常画面へ内部値を表示しない |
| `owner_id` | 認証済み利用者またはtenant。session IDを代用しない |
| `completion_key` | 同じ完了検索の重複保存を防ぐ一意キー |
| `completed_at` | 検索が正常完了した日時 |
| `expires_at` | `completed_at` から30日後の物理削除期限 |
| `summary` | 一覧表示用の商品種別または自然文の短い要約 |
| `source_text` | 利用者が入力した自然文のスナップショット |
| `condition_snapshot` | 確定した条件と価格の利用者向け表示値 |
| `reference_image_mode` | 参考画像を比較に使用したかどうか |
| `reference_image_refs` | 使用した4画像への所有権付き参照。未使用時は空 |
| `ranking_profile_id` | 保存時に使った固定 `typed-ranking-v4`。別profileを同じ表示schemaへ混在させない |
| `candidate_limit` | 確認画面に表示した比較候補上限 |
| `compared_count` | 実際に比較できた件数 |
| `result_snapshot` | 順位付け済み `HistoryProductView` 全件 |
| `schema_version` | 表示スナップショットのmigration用version |

`completion_key` はowner内でuniqueとし、完了通知やページ再読込が重複しても1項目だけ保存する。表示用スナップショットは保存後に採点し直さないimmutable dataとする。表示件数、カードの開閉、一覧の読込状態は保存対象にしない。

`completed_at` と `expires_at` はtimezone-aware UTCで保存し、`expires_at = completed_at + 30 days` とする。通常画面では利用者向けタイムゾーンへ変換して分単位で表示する。

### 16.2 `HistoryProductView`

商品ごとに、順位、商品名、表示画像、保存時点の価格、外部商品リンク、`confirmed`・`uncertain`・`contradicted` の必須状態、条件との近さ、typed decisionから作る一致・未確認・情報矛盾・不一致、避けたい条件への該当、画像比較利用の案内を保存する。raw score、内部component、正規化weight、evidence、registry、採用言語、TF-IDF、CLIP、pHash、Hamming距離は表示スナップショットへ入れない。

一覧APIは `history_id` を直接表示せず、serverが発行する推測困難な公開用locatorと一覧表示値だけを返す。詳細APIはownerを再検証し、通常画面用のallowlist modelだけを返す。郵便番号、お届け先、検索要求parameter、provider、model、prompt、token、digest、request IDは履歴表示モデルへ含めない。

### 16.3 保存と削除

現在結果のスナップショットは、利用者が `結果を見る` を選べる時点までに整合した状態で保存する。履歴項目への関連付けは同じ完了処理で試みるが、関連付けだけに失敗した場合も現在画面の結果を消さず、再保存できる状態を返す。再保存は外部検索や採点を実行しない。

個別削除はownerを検証したうえで、履歴項目、結果スナップショット、その履歴だけが所有する生成画像を一つの操作単位として物理削除する。複数履歴から参照されるassetが将来導入された場合は参照数を管理し、別履歴が使うassetを削除しない。失敗時は履歴項目を残し、部分削除を成功として返さない。

履歴は `completed_at` から30日間保持し、cache TTLとは独立して判定する。現在時刻が `expires_at` へ到達した履歴項目、結果スナップショット、専有生成画像は、期限削除処理が同じ操作単位で物理削除する。期限削除は冪等にし、失敗した項目は再試行対象として残すが、期限後の一覧・詳細APIへは返さない。期限切れデータを外部検索や採点で再構築しない。

### 16.4 実装済みのSQLite version 2

`SqliteSearchHistoryRepository` は呼出元が指定する新規または既存のローカルSQLite fileを使い、`PRAGMA user_version = 2` と次の2 tableを管理する。version 2はtyped表示snapshotだけを受理し、旧 `user_version=1` は内容を変更・削除せず固定storage errorで拒否する。

| table | 主なfield | 役割 |
|---|---|---|
| `search_history` | 内部 `history_id`、公開 `locator`、`owner_id`、`completion_key`、UTCの `completed_at`・`expires_at`、入力payload SHA-256、表示用 `detail_json` とそのSHA-256 | owner内の完了一意性、30日期限、新着順一覧、保存JSONとdigestの整合検査を持つ履歴本体 |
| `history_reference_images` | 親 `history_id`、0〜3の順序、公開画像locator、固定angle、PNG metadata、SHA-256、最大2 MiBの512×512 PNG BLOB | 履歴だけが所有する画像。schema 2.0は固定4方向、3.0は参考画像1枚。親削除時にforeign key cascadeする |

schema 2.0の `SearchHistoryWrite` はowner、completion key、UTC完了時刻、要約、元入力、typed表示条件、画像OFFまたは固定順4枚、固定 `typed-ranking-v4` profile ID、候補上限24または48、`results` または `empty`、必須状態を持つ最大48件の連続順位をstrict・extra-forbid・frozen modelで受ける。失敗・中止は入力値に持たない。同じowner・completion key・同じcanonical payloadは同じ公開locatorを返し、payloadが異なる場合は上書きせず固定conflictにする。別ownerの同じcompletion keyは独立する。

一覧・詳細・画像・個別削除はownerを必須とし、owner不一致、不在、期限切れを同じ固定not-foundにする。返却modelに内部ID、owner、completion key、provider、model、request、postal code、token、利用量、digest、raw scoreは含めない。保存と画像挿入、履歴と画像の個別・期限削除はそれぞれ単一transactionで、失敗時にrollbackする。期限到達後は `purge_expired()` の実行前でも一覧・詳細・画像から除外する。

新規POSIX fileは0600で作り、最終pathのsymlink・非regular file、groupまたはother権限を持つ既存file、旧version 1または未知の `user_version`、version 0だが既存objectを持つDB、必須table・columnの欠落、表示JSONと保存SHA-256の不一致を固定storage errorで拒否する。これはlocal・単一fileのoffline境界であり、認証・tenant解決、owner別OS領域、複数worker・共有DB、backup、at-rest暗号化、容量制限、定期purge、production migration、legacy現行pipelineからの自動保存、HTTP API・UIを提供しない。legacy cacheを読み書き・移行・削除しない。

## 17. ローカル検索jobの論理モデル（SQLite repositoryを実装）

`SqliteSearchJobRepository` は履歴DBやlegacy cacheとは別のローカルSQLite fileを使い、`PRAGMA user_version = 1` と単一の `search_jobs` tableを管理する。このDBはlocal単独利用、単一host、単一process、worker 1本だけを対象とする。保存するのは実行管理用metadataであり、検索結果の正本ではない。

| field | 内容 |
|---|---|
| `job_id` | DB内部だけで使うrandom ID |
| `locator` | 呼出元へ返す推測困難な公開locator |
| `owner_id` | server-side固定の `local-user` |
| `binding_sha256` | 同じ承認済みruntime bindingの二重投入を防ぐdigest |
| `status` | `queued`、`running`、`cancel_requested`、`succeeded`、`failed`、`cancelled`、`timed_out` |
| `revision` | transaction更新ごとに増える楽観的競合検出値 |
| `created_at`・`updated_at` | timezone-aware UTCの作成・最終更新時刻 |
| `start_before`・`started_at` | queued jobの開始期限と実際の開始時刻 |
| `cancel_requested_at` | 取消要求時刻。queued取消またはrunning協調取消に使う |
| `finished_at`・`purge_after` | 終了時刻と30日後の削除期限 |
| `result_locator` | 成功時に既存履歴等の保存済み結果を指すlocator。結果本文は入れない |
| `failure_code` | `execution_failed`、`queue_start_expired`、`worker_restarted` のいずれか |
| `record_sha256` | canonicalな行modelをdomain-separated SHA-256へ結ぶ改ざん検査値 |

同じ `owner_id`・`binding_sha256` はuniqueで、同時投入しても1 jobだけを作る。別の実行を望む場合は、別の明示承認から新しいbindingを作る。callback、approval token、検索文、商品、画像、provider URL・要求・応答、credential、例外本文は保存しない。SHA-256を匿名化として扱わない。

queued jobは作成から24時間以内にworker開始できない場合だけ `timed_out` へ移る。開始済みcallbackにはruntime timeoutを設けず、取消はcallbackが `SearchJobControl` を確認する協調方式である。取消後にcallbackが結果を返しても成功結果を採用しない。自動retryは行わない。

process再起動後はcallbackを復元できないため、残ったqueued・running jobを `worker_restarted` の固定失敗、`cancel_requested` jobを `cancelled` へ原子的に移す。外部処理を推測して再実行しない。終了jobは `finished_at` から30日後に明示的な `purge_expired()` で削除でき、期限後はcleanup前でも個別取得へ返さない。

新規POSIX fileは0600で作り、symlink・非regular file、groupまたはother権限を持つ既存file、未知schema、既存objectを持つversion 0 DB、必須column欠落、row modelまたはdigest不一致を固定storage errorで拒否する。全取得・取消・件数照会はownerを必須とする。ただしownerは認証結果ではなく固定local値である。local ASGI APIはこの固定ownerで既存repositoryを呼ぶが、DB schemaを変更しない。複数executorを同じDBへ接続する運用、共有DB、backup、暗号化、定期purge、公開HTTP server、現行CLI・次期フロントエンド接続は提供しない。

## 18. Counterfactual development較正artifact（テスト専用JSON）

`tests/img/counterfactual-development-001/` と `counterfactual-development-002/` は、製品DBや検索履歴ではなく、EXEC-065のdevelopment較正を再現するlocal fixtureである。各directoryの `manifest.json` はschema version、case ID、role、source case IDとそのmanifestのSHA-256、条件一覧、参照画像、候補label、生成call数、retry数、人間確認状態、CLIP実行前のlabel固定状態を持つ。参照画像recordはrelative path、role、任意のcondition IDと固定operation、source file SHA-256だけを保存する。pixel SHA-256とpHashはtest時に画像から再計算し、重複閾値へ照合する。provider request ID、生prompt、credential、候補商品URL・ASIN・商品名は持たない。

`tests/img/counterfactual-calibration-result.json` は上記2 manifest、固定counterfactual profile、固定CLIP runtimeをdigestへ結び、条件別の候補score、label数、pairwise AUC、中央値、診断閾値、balanced accuracy、適格性、採否を保存する。全体には適格条件poolとcategory集約の指標、事前基準、`overall_assessment`、`qualified_for_ranking` を持つ。不適格条件を除外して合格へ丸めず、development不合格時は診断閾値をproduction profileとして扱わない。

`tests/img/counterfactual-redesign-result.json` は、新しい画像やprovider応答ではなく、同じ2 manifestを再利用した初回方式とmean-positive再設計の比較記録である。development dataset・label・評価contractのSHA-256、外部call 0、再利用状態、両仕様の正解数・評価件数・accuracy・pairwise AUC・worst-condition AUC、再設計の条件別指標、絶対失敗理由、strict selectorの相対合格結果を持つ。score profile digestは式と固定parameterの同一性を表すが、production ranking profileまたは独立holdout合格を表さない。

`tests/img/counterfactual-v4-result.json` は同じbindingでmean-positive v2とminimum-positive v4を比較する後続記録である。v4の条件別・pool指標、正解数、絶対失敗理由、棄却した参照自己較正の集計、strict selectorによるaccuracy優先の相対合格を持つ。候補scoreや画像を複製せず、固定runtime testが元fixtureから集計値を再現する。v4 profile digestもproduction ranking適格を表さない。

`tests/img/counterfactual-v4-calibration-result.json` はminimum-positive v4へlabel-freeの観測範囲較正を重ねたdevelopment記録である。score・calibration profile digest、共通閾値0、条件ごとの観測範囲、center、half span、較正状態、適格条件20判定の集計と未較正v4との相対選択を持つ。候補単位score、画像、商品識別子、正解label本文は複製しない。色・メッシュのclass不足と独立holdout未実施を絶対失敗として残し、`qualified_for_ranking=false` を維持する。

`tests/img/image-holdout-006/` は未知のデスクライト・クランプ条件を使った独立1-case probeである。`collection.json` はURL・商品名・商品識別子を持たず、browser navigation、外部要求上限と送信・遮断件数、candidate ID・相対path・画像SHA-256・元寸法だけを保存する。`labels.json` はscore前に固定したmatch・mismatch・ambiguous規則と件数、`references.json` はテスト用gpt-imageのexact call上限・使用数・retry・候補非送信・人間確認状態と2画像の相対path・SHA-256を持つ。`result.json` は候補別scoreを複製せず、固定runtime・score・calibration profile digest、共通閾値0、観測範囲、label別件数・最小・中央値・最大、混同行列、accuracy、pairwise AUC、事前基準、不合格判定、ranking不適格を保存する。

このartifactはimmutableなDB recordではなく、testが全field、digest、画像binding、記録済みscoreを再検証するversioned JSON fixtureである。候補画像・参照画像のbinaryは既存のlocal test directoryだけに置き、生provider応答、利用者検索入力、商品本文、商品識別子をJSONへ保存しない。本番Cloudflare、検索履歴、利用量ledger、ranking profile、legacy cacheへ自動移行・接続しない。

再設計との相対合格fallbackは、永続DBではなく `CounterfactualDevelopmentMetrics` と `CounterfactualDevelopmentSelection` のstrict frozen modelで扱う。metricsは仕様ID、絶対判定 `fail`、development dataset・label・評価contractのSHA-256、正解数、評価件数、pairwise AUC、worst-condition AUCを持つ。比較する2件はdigest 3種と評価件数が同一でなければならない。selectionはpolicy ID、`pass`、`relative_development_accuracy`、使用したtie-breaker、勝者・敗者仕様ID、勝者accuracy、独立holdout進行可、ranking不適格を持つ。v2とv4の記録は第1指標 `accuracy` でv4を選んだ。検索文、候補、画像、provider metadataは受け取らず、検索履歴やproduction ranking profileへ保存しない。

## 19. 暫定counterfactual production artifactと別系統の永続化

EXEC-080の [先行1枚確認後の生成フロー](../SEARCH-FLOW.md#4-step-2-参考画像を確認する) は、了承した参考画像を保持し、条件別偽画像だけを追加する。coreの新規 `SearchHistoryWrite` と `HistoryDetail` はschema 3.0で参考画像1枚を保存する。DB `user_version=2` の既存先頭slot・angle `front_three_quarter` は互換用の保存位置であり、実画像の角度の証明ではない。旧schema 2.0の4枚は引き続き読める。暫定schema 5.0はdesired＋条件別counterfactualを維持する。DB migration、旧rowの変換、旧承認の再利用は行わない。

EXEC-066で追加したschema 1.0のCloudflare counterfactual request・artifact、provisional image batchとschema 5.0 ranking batchは、既存4方向artifactと別のstrict modelである。既存SQLite `user_version=2` の `history_reference_images` は固定angle slotを持ち、条件別counterfactualの保存には使わない。旧row、旧BLOB、旧completion keyを新schemaへ変換せず、既存DBの `user_version` も変更していない。

新artifactはcondition set、Cloudflare request metadata、参照set、固定CLIP runtime、正規化商品、source `typed-ranking-v4`、provisional profileをdomain-separated SHA-256で結ぶ。画像body、embedding、商品画像URL、provider応答、credential、内部error本文はranking batchへserializeしない。商品画像取得失敗はmissing、較正不能はunknownとして保持し、数値0へ保存しない。

`provisional_approval_repository.py` は承認専用SQLite `user_version=1` を別fileに作る。recordはowner、session、condition set、reference set、request metadata、成功済みCloudflare reservation・usage policy・preimage binding、exact call数、発行・15分期限・消費時刻、raw tokenのdomain-separated SHA-256を保持する。画像body、prompt、利用者入力、credential、raw tokenは保存しない。consumeは `BEGIN IMMEDIATE` と `consumed_at IS NULL` の更新を同一transactionで行い、再起動後も最初の1回だけ成功する。旧state snapshotや別の `user_version=1` DBをこのschemaへ読み替えない。

新公開入口の `generate_provisional_images()` は、先行1枚を了承して偽画像だけを生成し終えた後だけ、このSQLite参照確認を発行する。`ProvisionalReferenceReview.image_review` は参考画像と偽画像の同一process内の生成証拠を保持するが、SQLiteの承認recordへ画像bodyを追加しない。評価参照のcall数は既存desired＋偽画像の `1 + N` を維持し、先行 `reference_image` 1 callと `counterfactual_images` N callsの成功予約を別々に検証する。過去attemptは生成全体の利用量として保持し、この評価参照件数には含めない。4方向の利用予約は作らない。

`provisional_history_repository.py` は別fileのSQLite `user_version=5` を使い、provisional profile ID、known holdout accuracy 0.875、ranking profileとdigest、condition/reference/runtime binding、source ranking batch digest、各商品の必須状態・画像component状態・表示scoreを保持する。reference BLOBはposition 0のdesiredと、position 1〜3のcondition ID順counterfactualだけを許可する。履歴1件の削除または30日期限削除は外部キーcascadeでその参照BLOBも同じ単位で削除する。owner内completion keyは同一payloadだけ冪等、owner分離、再起動読込、一覧・詳細・画像取得を実装した。商品画像URL、embedding、候補画像digest、生provider応答は保存しない。旧history version 2からmigrationせず、両readerは相手のDB versionを拒否する。

EXEC-082ではregistry IDがdefault-attribute-registry-v2、商品証拠profileがbounded-product-evidence-v2となる。新規要求・判定は新digestへbindingし、旧計算結果の再利用を拒否する。既存のschema 5.0表示履歴と生成画像は書き換えず、旧ランキングを修正後の結果として再表示しない。


## 検索専用属性の保存境界

EXEC-083のBonsai候補は任意の `attribute_definition` にlabel・meaning・source_quoteを持つ。`TypedRequirementProposal` は検索専用registryを含み、その内容と `registry_sha256` の一致を検証する。intent・proposal・要求schemaのdigestが変わるため、変更前の保留承認を再利用せず条件確認から作り直す。共有registryは書き換えない。

EXEC-084の共通registryはcommon-attribute-registry-v3、商品証拠profileはbounded-product-evidence-v4。旧カテゴリ専用keyを現行要求へ暗黙変換しない。変更前の保留承認と再計算cacheは再利用せず、条件確認から作り直す。core履歴の表示snapshotには追加属性の名前・条件・判定説明を保存する。既存のSQLite表示schemaと過去データは移行・再採点せず、表示履歴から実行用registryを復元することもしない。暫定schema 5.0は従来の表示項目とtyped ranking digestを引き継ぐ。


EXEC-091では共通形状alias追加によりcommon-attribute-registry-v4へ更新した。検索専用registryにも同値のインチ・時間単位aliasを含めるため、該当定義のregistry digestが変わる。既存表示履歴・SQLite schemaは書き換えず、条件確認・実行用registry・prepared requestを新規生成する。過去snapshotの表示を現在の条件評価へ流用しない。


EXEC-093のrequest schemaは9.0で、request digest domainもv9とする。入力ごとに生成schemaの定数とdigestが変わり、送信直前に原文から再構成する。旧prepared requestを受理しない。明示属性のmeaningも原文ラベル・型・単位に結び付くため、検索専用registryとproposalのdigestが変わる場合がある。既存の表示履歴・商品cache・SQLite schemaは移行や再採点をせず、新しい推論・条件確認・承認から実行する。

省略された数量属性名のwireはproduct_name_ja・attribute_names_jaだけとし、backendが原文の固定事実と推論名を結合して完全定義へ展開する。meaningは仕様名と単位から構成し、数値・上下限・強さを再作文しない。原文のsource digest・元HTTP応答のresponse digestと、展開後intent・registry・proposalのdigestを別に保持する。prompt digestは実際に選択した固定promptへ結び付く。既存の履歴・cacheを移行や再採点しない。

EXEC-094は省略仕様名用promptと受信時の名前検証を変更する。wireとrequest schema 9.0は維持し、変更したprompt digest/body digestを送信前に再照合する。旧promptで準備した要求は再作成を必要とする。既存履歴・商品cache・SQLite schemaは変更しない。

EXEC-094の継続修正で、日本語文字・100文字上限・単位名除外を生成patternにも適用した。生成schema/bodyのdigestが変わるため、変更前のprepared requestは再構築が必要である。wireとrequest schema 9.0、表示履歴とSQLite schemaは維持する。

### EXEC-096の未確定候補と旧確認データ

DB形式の変更はない。数値属性の推論候補はintentのtyped_conditionsへ確認用として残るが、原文の属性名と数量の明示対応がなければblockingとして再構築する。未確認候補は検索専用registry/requirementへ登録しない。typed adapter profile IDを `bonsai-candidate-evidence-gated-v2` へ変更したため、旧proposalのprofile digestと旧承認artifactは再利用できない。実行前に現行proposalとqueryを再検証し、保留を解消した修正入力から新しい確認を作る。過去の表示履歴は過去結果として残し、新しい実行の承認には使わない。


## Candidate画像付き履歴のprofile拡張（EXEC-101）

既存SQLite user_version=5のtable・index・payload digest形式を維持し、表示JSONのranking_profile_idにcandidate-semantic-clip-v1を追加する。このprofileではknown_holdout_accuracy=nullのみ、既存typed-ranking-v5-counterfactual-provisionalでは従来の0.875のみを受け付ける。provisional_profile_idは画像評価部品の識別子として既存値を保持し、履歴一覧にも未測定nullを渡す。

source_typed_ranked_product_batch_sha256は互換field名を保持するが、新profileでは元CandidateRankingのdigestを格納する。元result全体やBonsaiの本文を履歴表示JSONへ保存しない。条件/参照/runtime digest、商品ごとの数値適合状態・画像状態・画像点数・合成点数と画像2〜4枚を保存する。completion_keyは新profileと確定画像付きresultのdigestに結び付け、保存だけの再試行を冪等にする。

旧行の移行は不要で、既存profileの読込・保存は維持する。新profileとnullを知らない旧binaryは新行を読めないため、導入時はcandidate専用DBを指定し、旧readerへ渡さない。既存DBの内容は今回変更していない。30日保持、owner分離、画像削除連動、保存のtransaction・同一key競合検証は既存repositoryを再利用する。途中のflow状態・生承認tokenは履歴に保存しない。


### candidateの単語一致採点と旧履歴

2026-09-10のcandidate結果は `candidate-confirmed-lexical-v2`。商品ごとに既存のTypedProductEvaluationと0〜1のlexical_scoreを持ち、semantic_score/semantic_assessmentと商品採点用Bonsai要求・応答hashを除去した。旧candidate中間結果を新形式へ暗黙変換せず拒否する。

最終採点は `candidate-lexical-clip-v2`。タイトル単語一致80%＋CLIP20%、画像不明時は単語一致のみとし、条件判定を先に比較する。completion_keyとprofile hashで旧採点から分離する。表示用schema5 SQLiteは変更せず、新profileを許可しknown_holdout_accuracy=nullを必須にする。旧candidate-semantic-clip-v1履歴は旧点数とprofileのまま読込可能。既存データの削除・再採点・table移行は行わない。


### candidateの検索語候補と選択

CandidatePlanは任意のquery_expansionと最大8件のquery_options、selected_query_indexを保持する。query_expansionはbonsai-query-terms-v2、原文/要求/応答digest、ready/unavailable、original_enと最大3件のsynonyms（ja/enの対）を持つ。各enは1文字列またはnullであり、対応のない英訳リストを許さない。失敗時はterms=nullであり、本文や例外を診断へ保存しない。候補の正規化・状態と値の対応、原文digest、選択indexと実行queryを検証する。Outscraper requestはquery plan digestだけでなく、選択queryから再構成した要求全体との一致を必要とする。

EXEC-124のブラウザ接続試験では、serverが `plan_lifetime=None` を指定した計画に限り `CandidatePlan.expires_at=null` とし、全体期限を持たない。この値もplan digestに含める。既存の診断入口は既定15分であり、保存planだけを再開権限にしない。画像のsingle-use承認期限と履歴DB schema 5は変更しない。

候補はBonsai商品評価の復活ではなく、確認用の検索語だけである。画像・採点のintentには入れない。候補選択を含む計画digestが旧承認の流用を防ぐ。元queryを含む候補から1本/24件だけを実行する。旧候補なしの中間計画JSONとbonsai-query-terms-v1を暗黙移行せず、新計画の作成を必要とする。表示履歴のschema/tableは変更しない。


### 辞書候補の中間計画

EXEC-103では `CandidatePlan.source_structure` に正規化前後の原文と商品句/修飾/依頼述語の範囲、parser版を保持する。ログや外部送信へ流用せず、JSON復元でsource_sha256との一致と範囲を検証する。query_expansionは `dictionary-query-terms-v1` を追加し、dictionary_sha256/sense_model_sha256/selected_sense_idを保持する。readyには選択ID、unavailableにはIDなしを要求する。旧Bonsai profileと混在/自動変換しない。新fieldにより更新前の中間計画digestは変わり、承認は再取得する。完了済み表示履歴のschema/tableは変えない。

ローカル辞書SQLiteは検索履歴とは別の再生成可能な資材。schema version 1でsense、正規化したlookup form、原典hashのmetadataを持つ。原典を更新するときは新規directoryへ再生成し、runtime-manifestと候補計画の辞書hashを更新する。旧履歴を再解釈・再採点しない。


EXEC-103の文脈選択追加では、ローカル辞書SQLiteのversion 2に語義ごとの日本語定義・用例contextを持たせる。旧version 1は旧方式で読取可能、新方式は新directoryへ再生成する。manifest schema 2は辞書・encoder・tokenizer・configのhashとscorer識別子を固定する。query_expansion `dictionary-query-terms-v2` はresolution_methodと任意resolverのprofile/model・要求・応答hashを追加する。bonsai方式には全resolver由来を要求し、旧profileへ新metadataを混入させない。新計画digestで承認を取り直し、完了済み表示履歴schema/tableは変更しない。


### 商品名候補reviewの追加

CandidatePlan.product_reviewはProductPhraseReviewまたはnull。原文hash、ProductStructure、product_name、product-query-terms-v1のQueryExpansionを保持し、planのsource/structure/expansionと一致を検証する。原文上の商品句と検索用候補を同一fieldへ上書きしない。未確認生成名はresolution_method=bonsai_proposal、辞書0件からの直接推論はbonsai_inferenceとし、どちらもselected_sense_id=nullで辞書選択と分離する。bonsai_inferenceはproduct-query-terms-v1だけで許容し、model/request/response hashを必須とする。原文上の対象と異なる語尾の生成名も候補として保持するが、元の構造は維持し、候補とQueryTermsの対応を検証する。辞書再照会で確定した見出しにはそのIDを残すが、原文との意味適合や商品性能の保証ではない。辞書DB/manifestと既存表示履歴DBのschemaは変更しない。新しいplanはdigestが変わるため再確認が必要で、古い承認を流用しない。


商品句候補のQueryExpansion.translationは省略可能で、OPUS-MTのprovider識別子、モデル/要求/応答SHA-256、ready/unavailableを保持する。EXEC-134以降は辞書候補0件のbonsai_inferenceと、候補ありからの未収録提案bonsai_proposalで使用できる。辞書選択や別profileへMT出典を付けること、unavailable時に英訳を持つJSONは拒否する。省略された旧JSONはtranslation=nullで復元する。SQL schema変更や既存履歴の移行はなく、OPUS-MT設定時の要求識別product-phrase-local-mt-v3とtranslator識別子をhashに含めて旧構成の承認/cacheを分離する。商品取得cacheの版は変更しない。


### Candidate相対順位profile（2026-09-10）

新規中間結果はcandidate-confirmed-lexical-v3、最終結果/表示履歴はcandidate-lexical-clip-v3を使う。元語英訳のタイトル比較とrelative-image-v1の画像scoreを含む。旧v2中間/表示結果は旧profileのまま読込可能。新旧最終結果ではimage batch/componentの型とprofileを照合する。

RelativeImageBatchは各商品の計算元marginと参照/商品/画像/runtime digestを保持する。RelativeImageComponentはminimum_margin、image_score、usable_condition_count、scored/partial_conditions/missing_image/indistinguishable_referencesのreasonを持つ。旧minimum_calibrated_marginへ未校正値を入れない。表示履歴のprovisional_profile_idはcounterfactual-relative-v1、known_holdout_accuracyはnull。旧画像profileを新ranking profileに組み合わせるJSONは拒否する。SQL schema/tableや既存データを変更せず、保存済み点数を暗黙に再採点しない。

candidate実runnerはimage-scores.jsonへ数値・状態・digestだけの画像batchを保存する。画像本文、商品本文、credentialは含まず、校正/比較後にunknownだけが残り原因を追えなくなる問題を避ける。


### 属性別画像profile（2026-09-10、EXEC-104）

VisualConditionDraft/VisualConditionの任意focusはkind(shape/color/material/appearance)、target(最大120字の英語対象句)、scope(whole/part)を持つ。null/省略時はJSONへ追加せず、旧condition hashを維持する。focus付き条件はdigestが変わり再確認が必要。

AttributeImageBatchは元のRelativeImageBatch、shape_targetsのcondition ID/target SHA256、領域抽出runtime hash、各商品のShapeEvidenceを保持する。ShapeEvidenceは対象/候補mask/参照maskのdigest、形状margin、region_unavailable/reference_too_close/extractor_unconfigured/extraction_failed等のreasonを持つ。画像診断JSONへ原文・対象句・商品本文・mask画素を含めない。ランキングJSONのsource planは従来通りの内部contractである。

最終順位candidate-attribute-image-v1と表示履歴counterfactual-attribute-v1を対応づけ、known_holdout_accuracyはnullとする。新旧profileを混在させる改変は拒否する。SQLite schema/tableを変更せず、旧結果は旧score/profileで復元する。


EXEC-106ではSQLite user_version=5と既存表示列を維持したまま、candidate-attribute-image-v2 / counterfactual-attribute-v2の対応を追加する。旧v1と混在させず、known_holdout_accuracyはnull。画像証拠には測定種別・希望方向・候補/参照の数値・保留理由を追加し、plan、runtime、profileのdigestで旧解釈と区別する。既存履歴の再採点や承認の再利用は行わない。旧focusのmeasure/direction未指定はJSONへnullを追加せず従来のdigestを保持する。


### 汎用外観profile（2026-09-10、EXEC-113）

EXEC-113のCLIP外観結果はcandidate-appearance-v1、画像batchはappearance-image-v1、表示履歴はcounterfactual-appearance-v1。AppearanceImageBatchはwhole_image_similarityのevidence_scopeを固定し、旧relativeの数値/状態/digestと別profile hashを持つ。部位の測定証拠は付与しない。新旧のranking/batch/history profile混在は拒否する。known_holdout_accuracyはnull、SQLite user_version=5と既存table/列は維持する。旧結果は旧profileのまま復元し、新方式へ再採点・再保存しない。新しい画像要求bindingは採点modeを含む。


EXEC-116のcandidate新規既定はcandidate-siglip2-appearance-v1、画像batchはsiglip2-appearance-image-v1、履歴はcounterfactual-siglip2-appearance-v1。Siglip2AppearanceImageBatchはwhole_image_similarityを固定し、SigLIP専用runtime/score profileとの対応を検査する。candidate/history profileの取り違えは拒否する。known_holdout_accuracyはnullを維持し、試験75.8%を全履歴の保証値へ埋め込まない。DB schema5の列変更や旧行の再採点は行わず、新completion keyとruntimeで新規保存する。旧CLIPのcache/埋込みはSigLIPの768次元とruntimeに合わないため再利用しない。永続埋込みcacheの自動移行は追加しない。
