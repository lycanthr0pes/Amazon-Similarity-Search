# セキュリティ

## 1. 対象範囲

この文書は、現行のローカル実行向け amazon-explorer に実装されている保護と、運用上必要な制約を整理する。アプリの実装根拠は `src/config.py`、`src/clients/`、`src/repositories/cache_repository.py`、`src/ui/streamlit_ui.py`、次期domain境界は `src/search_v2/`、AIレビュー用の境界は `tools/ai_review/` と `tests/conftest.py` を正とする。現行Bonsai経路と次期検索の内部境界は [BACKEND.md](BACKEND.md)、利用者向けの確認順序は [SEARCH-FLOW.md](../SEARCH-FLOW.md) を参照する。

現行のStreamlit・CLIアプリケーションには、アプリ独自の認証、認可、利用者別OS永続領域、レート制限、監査ログはない。現行local productionは利用者判断によりper-user・session・day・cost quotaを設けない。次期検索には呼出元が渡すownerで論理分離するローカル履歴repositoryと、ownerを `local-user` へ固定するlocal job repositoryがある。local ASGI APIもownerをrequestから受けず、この固定値だけでjob・schema 5.0履歴を操作する。これは認証主体を決定する機能ではなく、現行Streamlit、最終承認controller、server起動構成にも未接続である。インターネットへ公開する前提の多利用者向けサービスではない。

### 1.1 local HTTP APIの境界

`src/search_v2/production_api.py` はASGI client addressがIPv4またはIPv6 loopbackの場合だけ処理する。proxy headerを信頼して公開元を判定せず、公開networkへbindする構成も提供しない。公開・多利用者化ではloopback判定を認証・認可の代替にせず、TASK-003で主体解決、CSRF、監査、rate limit、tenant別保存を設計する。

承認済み `ProductionSearchCommand` はHTTP bodyへ直列化しない。最終承認controllerが同一processのstoreへ最大15分だけ登録し、43文字以上のrandom capabilityを `X-Amazon-Explorer-Submission` headerで投入APIへ渡す。capabilityはURL、応答、reprへ含めず、job投入後はstore内のcommand参照を破棄する。同じcapabilityの期限内再送は既存jobを取得し、providerを再実行しない。未登録・期限切れは固定404とする。

job応答からowner、binding SHA、内部failure codeを、履歴応答からprofile、既知accuracy、digest、score、画像bodyを除外する。repository・serviceの例外本文は固定404、409、503、500へ写像し、全JSONへ `Cache-Control: no-store` と `X-Content-Type-Options: nosniff` を付ける。HTTP APIのoffline testは注入fakeと手動ASGI scopeだけを使い、credential、provider、browser、委託フロントエンドを使用しない。

## 2. 信頼境界とデータフロー

```text
利用者入力
  -> ローカルBonsai OpenAI互換API
  -> 抽出した商品属性
  -> Outscraper API
  -> Amazon商品候補
  -> ローカルJSONキャッシュ
  -> Streamlit / CLI
```

守る対象は次である。

- `OUTSCRAPER_API_KEY`
- `CLOUDFLARE_API_TOKEN`
- 利用者が入力した検索条件
- Bonsaiが抽出した属性
- Outscraperの生レスポンスと商品URL・画像URL
- 一致、不足、除外条件を含む採点結果
- 内部パス、スタックトレース、外部サービスの診断情報

商品検索条件と結果はローカルキャッシュへ平文で保存される。キャッシュキーはSHA-256由来だが、暗号化や匿名化ではない。

## 3. シークレット管理

`src/config.py` のPydantic Settingsは、OS環境変数とプロジェクトルートの `.env` から設定を読む。Outscraper APIキーは `X-API-KEY` ヘッダーで送る。

現在確認できる保護:

- `.env` と `.streamlit/secrets.toml` は `.gitignore` 対象である
- `.env.example` は変数名だけを示し、実値を含めない
- APIキーをクエリURL、キャッシュキー、JSON payloadへ含めない
- Streamlitのサイドバーはキーの有無だけを表示し、値を表示しない
- APIキーが空ならOutscraperへのHTTP要求前に停止する
- Cloudflare API tokenは通常のglobal `settings` のfieldへ保持せず、live test開始時だけ専用 `CloudflareLiveSettings` の `SecretStr` で受け取る。live runnerのrepr・結果・固定例外・保存PNGへ実値を含めない
- 対話式の暫定ranking live E2Eは、Outscraper API keyを `SecretStr` にする専用loaderを人間による参照承認consume後にだけ呼ぶ。参照拒否、期限切れ、file改ざんではloaderを呼ばず、Outscraper・商品画像を0件にする

運用規則:

```sh
test -e .env || cp .env.example .env
chmod 600 .env
git check-ignore -v .env
```

- 実値をGit、Issue、Plan、WORKLOG、画面キャプチャ、シェル履歴へ記録しない
- 本番ではリポジトリ内ファイルより、実行環境のシークレット管理機構を使う
- 漏えいが疑われる場合はキーを失効・再発行し、履歴、ログ、キャッシュ、外部サービスの利用記録を確認する
- `.env` の権限はコードで強制されないため、配置時にOS権限を確認する

Cloudflareの初回live試験は、固定合成intentから作る基準画像1枚の1 callだけとする。`--run-live-api`と`--run-cloudflare-e2e`の両方を必須とし、retry 0、redirect無効、TLS検証有効、120秒transport timeout、4 MiB応答上限を維持する。生応答を保存せず、strict検証・metadata除去後の512×512 RGB PNGだけを指定された新規absolute pathへ0600でexclusive作成する。

2026-09-07の初回live試行は、上記条件と現行料金を再提示して明示承認を得た後、1 HTTP attempt・retry 0で実行した。12.43秒後に固定エラーとなり、PNGは作成されなかった。token、生要求、生応答、provider本文は表示・保存していない。この実行後、再通信せずに `configuration`、`output`、`transport`、`http_status`、`response_contract`、`image_content`、`unexpected` のclosed stage、検証済みHTTP statusまたはnull、request count、retry count、wall millisecondsだけを返すdiagnosticを追加した。過去の固定エラーは新しいstageへ推測で割り当てない。

同日の別承認による追加1 callは、28.246秒後に `image_content`、request count 1、retry 0で停止し、PNGを作成しなかった。このstageによりtyped transport、HTTP 200、exact success JSON envelopeまでは通過したと確定した。公式契約はBase64画像を返すが形式をPNGへ限定していないのに対し、当時のparserはdecode前からraw PNGを要求していた。512×512 JPEG fixtureが同じstageを再現したため、JPEG・PNG・WebPをbyte上限内で完全decodeし、単一frame・exact寸法を検証してからmetadataなしRGB PNGへ正規化するようoffline修正した。生画像を保持していないため実応答形式は断定せず、修正後のlive再試行も条件・費用を再提示した明示承認後だけ行う。

## 4. OutscraperへのAPIキー送信

### 4.1 endpoint

タスク作成前に `OUTSCRAPER_ENDPOINT` を次の条件で検証する。

- HTTPSである
- ホストが存在する
- URL内にusernameまたはpasswordを含まない

APIキー付き要求は `allow_redirects=False` で送り、HTTP 3xxを `OutscraperSecurityError` として拒否する。リダイレクト先へAPIキーを転送しない。

### 4.2 `results_location`

非同期タスクが返す `results_location` は外部入力として扱う。結果取得前に次を検証する。

- 文字列である
- HTTPSである
- ホストが存在する
- URL内認証情報がない
- 設定endpointとホストおよび実効ポートが一致する

末尾のドットとホスト名の大文字小文字を正規化し、既定HTTPSポートは443として比較する。条件を満たさないURLにはHTTP要求を行わない。結果取得もリダイレクトを拒否する。

この検証は同一オリジンへのキー送信を守るものであり、設定者自身が悪意あるendpointを設定することまでは防がない。`OUTSCRAPER_ENDPOINT` を変更できる権限を制限する。

次期v2の `outscraper_http.py` はさらに、承認permitに固定したcanonical HTTPS endpointと同じoriginで、初回応答と同じrequest IDを持つexact `/requests/{id}` だけを結果取得先として許可する。APIキーを送る前に毎回URLとparameterを再検証し、userinfo、query、fragment、別path、大文字・末尾dot等の非canonical authorityを拒否する。通信mockに加え、2026-09-06の明示承認済み単一試験でtask作成1回と同一taskのpoll 9回が成功した。別originや異常応答の実サービス試験は行っていない。

## 5. 再試行、待機、失敗分類

Outscraperで自動再試行するのは次だけである。

- `requests.Timeout`
- `requests.ConnectionError`
- HTTP 429
- HTTP 5xx

既定は最大3試行、基準1秒の指数バックオフである。その他の4xxは再試行しない。各HTTP要求の既定タイムアウトは30秒である。

非同期タスクは処理中、成功、失敗、不明へ分類する。`data=[]` は情報欠落や失敗ではなく正常な0件として扱う。既定のポーリング間隔は30秒、最大50回であり、上限後は `OutscraperTaskTimeoutError` とする。

再試行には現時点でジッターと `Retry-After` 対応がない。回数や取得件数を増やすと、課金、負荷、最大待ち時間が増えるため、設定変更時に確認する。

legacy現行検索のBonsai属性抽出POSTには既定60秒のタイムアウトがあるが、自動再試行はない。次期v2のrequest v9はapplication timeoutを設定せず、1予約を1回のtransport callへ固定して失敗をledgerへ記録する。応答しない場合は人間の手動停止まで待ち得る。再試行する場合の新予約・上限・backoffは未実装である。

次期v2のOutscraper境界は、承認済みtask作成GETを自動再試行せず、HTTP adapterのretryも0に固定する。`Pending` taskの結果取得だけを30秒間隔・最大50回で行い、最後のpoll後はsleepしない。通信・HTTP・応答不正・task失敗・待機超過でも開始済み1-call予約を `failed` として残す。明示承認済み単一試験ではtask作成1回・poll 9回で成功したが、失敗時のlive回復性、複数workerの利用量制御、production運用は保証しない。

## 6. レスポンス検証と例外

- BonsaiはJSON object、`choices`、`message`、非空の `content` を順に検証する
- Bonsaiの生応答を属性へ変換できない場合、固定文言のエラーにして生応答を例外メッセージへ含めない
- 次期のnetwork非依存adapterはfull raw response bodyをUTF-8・1,048,576 bytes以下に限定し、duplicate key、非有限数、Markdown fence、前後の説明文、JSON断片、unknown field、型coercionを固定エラーで拒否する。検索可能compact wireは最大12種類の固定field、確認待ちは `ambiguities` だけに分け、商品名等48文字、term 32文字、各term list・typed condition・set値4件、ambiguity 2件・各96文字を強制する。categoryはproduct nameへ、colorとfeaturesはtermsまたはtyped conditionへ集約し、省略値を完全19-field draftへ決定的に復元して再検証する。必須のmode・source、価格mode別の有効値、inferred confidenceなど意味のある欠落は拒否する。失敗時は列挙済み段階、正規化済みfinish reason、妥当なcompletion token件数、response byte数だけを保持する。draft schema不一致時だけ、`document`、`fields`、`price`、`typed_conditions`、`ambiguities`、`multiple` の固定groupも保持する。生本文、provider固有理由、検索文、field値、validation message・input・contextを保持しない。このadapterは現行検索へ未接続である
- 次期Bonsai request境界は固定promptだけをsystem messageへ置き、固定field branch、文字列・配列上限、ambiguity code pattern、同値のconverter互換decimal pattern、価格mode・source別8 sparse variantを持つ非空のcompact生成schemaを `response_format={"type":"json_object","schema":<生成用schema>}` へ含めるbodyをsource・model・response上限とv9 digestへ結び、loopback HTTPまたはcanonical HTTPSだけを許す。完全canonical schema本文はmodelへ二重送信せず、完全schemaと生成schemaのdigestを別々に保持する。生成用schemaは既知の矛盾を早期に防ぐ補助であり、application側の完全strict schemaを最終権威として、range順序や将来のvalidatorを含む不正値を後段へ渡さない。application `max_tokens` とHTTP timeoutは設定しない。Requests transportはこの契約を再検証し、環境proxy・`.netrc`・環境CA・既定header・cookieを使わず、TLS検証を有効化し、redirect・retryを禁止する。raw入力・prompt・body・responseをserializable descriptorや結果へ保持せず、圧縮応答、Content-Lengthまたは実測の1 MiB超過、利用量予約不一致を拒否する
- 本番 `llama-server` は `--cache-prompt` を明示して同一process内のKVを再利用する。`--slot-save-path` は設定せずdiskへslotを保存しない。cacheには処理中・直近の入力由来状態がmemory上に残り得るため、loopback bind、単一slot、同一OS userの信頼境界を維持し、process終了をcache破棄境界とする
- localhost Bonsai結合testは `live_api` と `bonsai_e2e` の二重marker、専用CLI opt-in、明示したabsolute server・model pathが揃う場合だけ起動する。使用中portを操作せず、server子processへcredentialを含む親環境を継承せず、loopback、log無効、slot非保存、合成入力2 calls、retry 0、response 1 MiB、ready後900秒全体deadlineに限定する。要求・応答本文とcache内容は保存・出力せず、test所有serverは成功・例外・deadlineの全経路で停止する
- EXEC-058の明示承認済みlive testは上記境界内の2 callsだけを実行し、両方のfull JSON・strict intent成功と2件目891 cached tokensを安全な集計で確認した。credential、外部network、課金、server log、slot保存、生要求・生応答の保存はなく、終了後にserver processなし・port 18080非listenを独立確認した
- EXEC-059の応答時間診断は専用CLI selectorで通常のBonsai live testを排他にし、同じ固定合成request v6を2回だけ送る。生応答はstrict adapterとmetadata投影の間だけmemoryに置き、`completion_tokens`、`prompt_n`、`prompt_ms`、`predicted_n`、`predicted_ms`、`finish_reason`、response byte数と既存prompt・cache token数だけをboundedに保持する。duplicate key、非有限数、負値、型coercion、token不整合、過大値、未知finish reasonを拒否し、入力、生成JSON、任意provider field、cache内容を結果・出力へ含めない。明示承認済みlive診断は2 callsともfull JSON・strict intentに成功し、2件目は923 / 924 prompt tokensをcacheした。credential、外部network、課金、retry、server log、slot保存、生要求・生応答の保存はなく、終了後にserver processなし・port 18080非listenを独立確認した
- EXEC-060のrequest v7はwireの既定値省略とminified出力指示だけを追加し、完全schema、本文非保持error、1 MiB上限、retry 0を維持した。196は固定代表fixtureのoffline形式目標であり、`max_tokens=196` を設定していない。後続の明示承認済みlocalhost診断では365.12秒で応答未完了となり手動停止したため、strict成功率、品質、速度は得られていない
- EXEC-061のrequest v8は固定field branchと文字列・配列上限をcompact modelとllama.cpp grammarへ反映した。代表fixtureは104 tokensだが任意出力のtoken上限ではない。承認済み2-call診断ではstrict intentとwarm 17.625秒、追加の承認済み1-call development regressionでは50.628秒・82 completion tokensを確認したが、後者は明示条件を欠落し、不正なtyped conditionによりblockingとなった。修正後は入力を語彙非依存の原子的条件へ分け、未知語を原文termsへ保持し、割当不能をblockingへ戻すよう要求する。typed attributeとvalue typeは生成schemaとadapterの両方で結ぶ。同一入力のrequest bodyは15,032 bytesから14,859 bytesへ減った。さらに承認済み1 callを実行し、53.595秒・248 completion tokensでstrict intentへ到達したが、価格・除外条件欠落と入力にないtyped conditionによりblockingで停止した。retry、Outscraper、credential、課金、外部networkはない。その後、requestを変えずに入力中の原語・trusted aliasでtyped conditionを根拠付けし、不正だがsourceに現れる値を自由語termへ戻し、明示JPY上下限と未知語を含む除外対象をsourceから決定的に復元するadapter境界を追加した。取得済み応答相当fixtureはreadyとなるが、adapter修正後の再推論は未実施である。旧v7 descriptorはv8 digest domainで拒否し、offline結果をproduction成功として扱わない
- 日本語のsource groundingと否定対象抽出はSudachiPy `SplitMode.C` の全形態素、品詞、NFKC/casefold済みsource offsetへ統一する。typed valueとtrusted aliasは完全な連続形態素spanにだけ一致させ、未知複合語内の単一漢字部分一致、格助詞より前の語の巻き込み、二重否定を拒否する。価格数値の有界正規表現と英語ASCII語境界は別責務として維持する
- SudachiPy修正後の最初の承認済みlocalhost 1-call試験は、strict intent・typed proposal・query plan作成後の集計コード不備で結果未確定となり、自動再実行しなかった。修正方法をoffline確認して別の明示承認を得た追加1-callは83.398秒、902 prompt tokens、290 completion tokens、response 1,895 bytesで完了し、未知語2種、明示JPY範囲、除外対象、二重否定拒否、ready proposal、query planの固定判定がすべて成功した。各試験は1 call・retry 0であり、Outscraper、Cloudflare、credential、外部network、課金はなく、各終了後にserver停止・port非listenを確認した。生要求・生応答・server logは保存していない
- 後続の一続きE2E第1段階では、別の承認済みBonsai 1 callが入力にない商品名を生成し、明示価格と未知色を欠落させても `ready` となったため、query確認時にOutscraper前で停止した。adapterは商品名、brand、model number、自由語termを入力中の完全なSudachiPy spanまたはASCII語境界へ照合し、無根拠値を削除する。入力に根拠のある商品名、brand、model number、required term、preferred termが1つも残らない場合は固定messageのblocking ambiguityへ戻し、queryと後続provider予約を作らない。商品名がなくても根拠のある肯定検索語が残る場合は、人間の第1確認へqueryを提示できる。URL値は削除で隠さず既存の固定searchability errorにする。正しい3桁comma区切りのJPYだけを復元し、不正区切りへ部分一致しない。このfail-closed境界もproviderが黙って省略した全条件を検出・復元する保証ではない
- query確認では、SudachiPyが分けた連続接頭辞を捨てて検索条件を弱めない。接頭辞は直後の内容語と同じtokenへ結合し、queryとrankingで共通利用する。旧queryを持つ一時継続stateは後続providerへ渡さず削除する
- EXEC-064の画像検索診断は、隔離したChromiumでAmazon.co.jp検索結果へ1回だけ遷移し、外部request 59件、retry 0、detail page・login・cookie引継ぎ・CAPTCHA回避なしで候補画像4件を保存した。URL、ASIN、商品名、raw DOM、cookie、credentialは保存していない。独立参照はテスト用の組込みgpt-imageを4 callsだけ使い、商品候補画像をgeneratorへ送信せず、repo credentialも使用していない。画像と集計JSONはlocalのGit未追跡領域だけに置いた。本番の4方向参照providerはCloudflareとし、gpt-imageをproduction経路へ接続しない
- 後続browser試験はperformance logをbatchで取得したため、承認した外部request上限100件に対して停止時の観測値が111件となった。上限超過を成功扱いせず、候補保存、retry、gpt-image、CLIPを開始しなかった。次の実試験では、local模擬ページで上限どおりのserver到達を確認したCDP送信前interceptionを必須にし、実行ごとに新しい明示承認を得る
- 別承認後のCDP interception試験は外部到達を100件へ固定し、追加64件を送信前に遮断した。7候補を保存したが正例0件・負例7件で最低構成に達しないため、retry、gpt-image、CLIPを開始しなかった。商品URL、ASIN、商品名、生DOM、Cookie、credential、生provider応答は保存していない
- category-only条件の別承認試験もCDP interceptionで外部到達を100件へ固定し、追加70件を送信前に遮断した。保存した10候補はCLIP前に正例4・負例6へ固定し、候補をgeneratorへ送らずgpt-imageを4 calls・retry 0だけ使用した。URL、ASIN、商品名、生DOM、Cookie、credential、生provider応答は保存せず、生成参照、候補画像、manifest、集計結果だけをlocalのGit未追跡領域へ置いた
- 次期Cloudflare HTTP境界は `image_generating` state、開始済み4-call予約、request metadataを送信前に再検証し、account IDとAPI tokenをserver-side引数からexact endpointとAuthorization headerへだけ注入する。prompt-onlyを含めmultipartを使い、新規Session、環境metadata除去、TLS検証、redirect・retry禁止、120秒timeout、identity encoding、4 MiB応答上限を固定する。exact JSON envelope、canonical Base64、2 MiB以下のJPEG・PNG・WebPだけをmagicとPillow formatで受理し、完全decode・単一frame・512×512を検証してmetadataを除いたRGB PNGへ再encodeする。1件でも失敗した場合は一部画像を返さず予約を `failed` にする。形式正規化の修正後はmock・合成画像でだけ確認しており、実Cloudflare、課金、画像品質、現行検索には未接続である
- 次期Outscraper HTTP境界は承認permit・開始済み予約・request parameterを送信前に再検証し、API keyを `X-API-KEY` にだけ注入する。要求ごとの新規Sessionから環境proxy・`.netrc`・環境CA・既定header・cookieを除き、TLS検証、redirect・retry禁止、30秒timeout、identity encoding、8 MiB上限を固定する。task ID・status・結果URL・poll IDをstrictに検証し、生provider文・query・URL・API keyを固定例外へ含めない。明示承認済みの固定合成queryによる単一live試験はtask作成1回、poll 9回、候補24件で成功し、全候補が正規化契約を通過した。生応答と商品識別情報は保存していない。現行検索、API、UI、production E2Eには未接続である
- 次期ranking境界はstrict intent、query plan、normalized product batch、readyなtyped proposal、固定registry・product evidence・typed ranking profileを再検証し、digest不一致や偽装済みnested instanceを生入力のない固定errorで拒否する。schema 3.0のoffline後半pipelineへ接続済みだが、legacy現行検索・API・UIへは未接続である
- 次期orchestration境界は各stage、owner・session、revision、request・plan・typed proposal・runtime digest、利用量予約を再検証する。typed proposalをqueryより先に確定し、readyはquery plan・digest必須、blockingはquery fieldを持たない専用第1確認とquery digest不在を必須にする。blocking確認から画像生成または画像なし続行へ進む操作は追加provider予約前に固定errorで拒否し、旧schema、query付きblocking、queryなしready、ranking-v3 runtimeも拒否する。第1確認前のCloudflareと最終承認前のOutscraperを呼ばない。credentialは実行関数の非保存引数から既存transportへだけ渡し、検索承認tokenは非repr objectだけに一時保持する。provider失敗は生応答を含まない固定結果へ変換し、single-use tokenの再利用を次の予約・transport前に拒否する。この境界もmock・fixtureだけで確認しており、実provider、現行検索、API・UIには未接続である
- OutscraperはJSON objectを要求し、完了応答の `data` がリストであることを検証する
- Outscraperの通信、応答、危険なURL、タスク失敗、待機超過を別の例外型で区別する
- 外部データは正規化後にPydanticモデルへ変換し、後段の採点と表示へ渡す

現行legacy Outscraperのタスク失敗例外は、外部レスポンスの `description` または `message` を例外文へ含め、レスポンス辞書を例外属性へ保持する。これらは信頼できない外部データであり、ログ転送や利用者表示へ使う場合はマスキングと改行等の正規化が必要である。未接続のv2境界は生provider文を例外へ含めず、固定メッセージだけを返す。

## 7. ログと画面への情報開示

現行の標準出力には次が出る。

- パイプラインの段階
- Outscraperのrequest ID
- ポーリング回数とstatus
- 保存または再利用したキャッシュのローカルパス
- CLIで表示する商品名、価格、商品URL

検索語、Outscraperの要求URL、`results_location`、APIキーは現行の標準出力へ直接出していない。

Streamlitは検索中の例外を `LOGGER.exception()` でサーバーログへ記録し、利用者には「検索に失敗しました。設定と外部サービスの状態を確認してください。」という固定メッセージを表示する。スタックトレースや内部例外を画面へ返さない。サイドバーにはBonsai base URL、Amazonドメイン、言語、取得件数が表示される。

サーバーログには外部例外の詳細やローカルパスが残る可能性がある。ログを外部へ転送する前に、保存先、アクセス権、保持期間、マスキング対象を決める。`SHOW_DEBUG_INFO=true` は重みを表示するだけで、APIキーは表示しない。

## 8. キャッシュの保護

キャッシュルートの既定値はプロジェクト内 `cache/` であり、Git管理対象外である。

現在実装されている保護:

- namespaceの絶対パスと `..` を拒否する
- キャッシュキーを空でない小文字16進数に制限する
- 同じディレクトリの一時ファイルへ書き、flush、`fsync`、置換する
- JSON破損、文字コードエラー、読込エラーをキャッシュミスとして扱う
- 属性、正規化、採点をPydanticモデルで再検証する
- Streamlitはセッションごとにランダムscopeをキーへ含める

現在実装されていない保護:

- キャッシュpayloadの暗号化
- 認証ユーザーまたはテナント単位の保存ルート
- プロセス間ファイルロック
- 容量上限、自動削除、全namespace共通の保持期限
- ファイル権限のコードによる強制
- 破損ファイルの隔離と監査通知

Streamlitのscopeは偶然のセッション間再利用を避けるためのキー材料であり、認証トークンやアクセス制御ではない。CLIは固定の `local-cli` scopeを使う。共有ホストではOSアカウントとディレクトリ権限で `CACHE_DIR` を保護し、Web公開領域や不要なバックアップへ含めない。

## 9. UIと公開範囲

現行Streamlit UIにはアプリ独自のログイン、権限確認、利用回数制限がない。検索はStreamlitの実行中に同期処理され、外部API利用を伴う。したがって、アクセス制御のない状態でインターネットへ公開しない。

商品画像と商品リンクはOutscraper由来の外部URLである。現行データモデルはURLスキームやホストを制限していない。信頼できない配信元を許容しない運用では、表示前のURLポリシーを別途実装する必要がある。

## 10. 変更時の確認

外部通信を起こさない回帰確認:

```sh
uv run --frozen --offline --no-sync pytest tests/test_outscraper_client.py \
  tests/test_bonsai_client.py \
  tests/test_cache_repository.py \
  tests/test_user_attribute_extraction.py
uv run --frozen --offline --no-sync ruff check .
git diff --check
```

テスト全体の通常ゲートでは、事前準備済み環境で `uv run --frozen --offline --no-sync pytest -m 'not live_api'` を使う。依存準備の `uv sync` は別工程であり、必要に応じてpackage indexへ通信する。`live_api` の扱いは後述の二重opt-inに従う。

手動確認:

```sh
git check-ignore -v .env cache/
git ls-files .env cache/
```

`git ls-files` は何も返さないことを期待する。実キャッシュ内容やシークレット値を確認出力へ貼り付けない。

## 11. AIレビューとテストの安全境界

### 11.1 信頼主体

candidate、candidate内のPython/task/prompt/AGENTS、model出力は非信頼である。信頼するのは、人手監査済みreleaseからroot-owned prefixへinstallしたstdlib launcher/preflight、manifestでdigest固定したruntime assetとOCI image、candidateと異なる非root coordinator、candidate外のledger/key/artifact root、人間の承認者である。

production launcherは `-I -S`、root-ownedでgroup/world writableでないPython prefixとstdlib pathを要求する。manifestをraw bytesで検証し、Python executable、harness、task、lock、schema bundle、public key、egress/pricing policyをimport前にopenしてSHA-256とinodeを固定する。現在実行中の `sys.executable` もmanifestのPython path、inode、digestへ一致させる。

productionで期待するmanifest SHA-256は、署名済みrelease record等の検査対象外anchorから受け取る。同じinstalled manifestを実行直前にhashした値だけでは、置換されたmanifestを自己承認してしまうためtrust anchorにならない。TaskSpecのfull strict validationは `runtime_release` builderのPydantic modelが担当し、task raw bytesとharness digestをmanifestへ固定する。external launcherのimport前stdlib検査はfull schemaを再実装せず、manifestが保持するtask FDのstrict JSON、v2、verified harness bindingだけをnarrow checkする。このnarrow check、manifest内digest、external approved manifest SHAの3つを別の責務として維持する。`runtime_release workflow-init` はこれらに加え、manifestに固定したpublic key、protected clean candidate、人手承認済みpatch SHAを再検証して最初のrequestを作る。credentialとnetworkは使わず、outputをexclusive作成後に0500/0400へ凍結する。

coordinator production runtimeは非rootのrootless Podman、user namespace、`keep-id`、有効なseccompを必須とする。Docker、rootful Podman、user namespaceなし、`unconfined` seccompへfallbackしない。Podman subprocessはpasswd HOMEから導出した明示 `HOME` / `XDG_CONFIG_HOME` / `XDG_DATA_HOME` / `XDG_RUNTIME_DIR` を共用する。HOME/XDG pathの全祖先はrootまたはlauncher user所有、group/world非writable、symlink/POSIX ACLなし、private leafはlauncher user所有であり、candidateは別UIDで所有・書込みのどちらもできないことを要求する。

launcher `--deployment-check` はcredential、workflow artifact、key、ledgerを受け取らず、installed TaskSpec v2とverified harnessのbinding、local 4 imageを `--pull=never` / `--network=none` で検査する。Podman infoのgraph root、run root、active storage config、seccompを含むstable subsetをimage検査の前後で同じcanonical environmentへ結び、変更時は停止する。active `storage.conf` の `imagestore` / `additionalimagestores` とgraph optionsの別imagestore指定も拒否する。成功status `nonlive_ready` はcredential-free preflightだけを示し、production E2Eやlive APIを示さない。

2026-08-16の承認済み配備では、`ai-review`（UID 1100）と `amazon-candidate`（UID 1101）を分離し、ai-review専用subuid/subgid、rootless Podman 6.1、user namespace、seccomp、passwd由来のprivate HOME/XDGを確認した。root-owned releaseは `/opt/amazon-explorer-ai-review/releases/dd4b6bde2bd2d7f3ebc67c5190949c1cc97652ee`、private stateは `/var/lib/amazon-explorer-ai-review` に分離した。manifest SHA-256 `703d2e183558afe6e52198247888675d7f0b526f5082051a9ae75d5ea3a402ae`、TaskSpec SHA-256 `8507bc001dcf4d383ce43cb335e65851da740c10d6e3c4dd752c1f762b1b32fd`、harness SHA-256 `0d27b9c541b01b1fb6f02c270286965c1507748abe5f5667ac5a9e7250426278` と4つの異なるimage digestを固定し、`--deployment-check` が `nonlive_ready` で成功した。

準備時には承認範囲内でpackage導入、public base image pull、image内package取得、4 image buildを行った。deployment check本体は `--pull=never` / `--network=none` であり、credential、OpenAI API、broker external network、live workflow、課金を使用していない。したがって、この成功を外部送信またはproduction E2Eの証拠として扱わない。

`/var/lib/amazon-explorer-ai-review/build/workflow-init-r2/initial` のroot所有build証拠はlive入力へ流用しない。external manifest/patch anchorを再照合し、local objectを共有しないUID 1100所有standalone candidateから `/var/lib/amazon-explorer-ai-review/artifacts/TASK-CANARY-001-live-init-r2/phase-request.json` を新規生成した。directoryは0500、fileは0400でUID 1100だけが読め、UID 1101は読めない。initializerはcredential、API、external networkを使っていない。

### 11.2 candidate、path、snapshot

candidateはlocal Git objectを共有しないstandalone canonical single-commit cloneに限定する。Git object、tree、commit、metadata、path、mode、owner、mount、hardlink/symlink、allowed/denied path、byte/line/file上限を検査し、content-addressed read-only snapshotへ固定する。

共通 `sensitive_paths` policyは任意階層の `.env*`、`.envrc`、`.streamlit/secrets.toml`、`cache` / `.cache`、`.git`、SSH/cloud/container/package-manager/provider credential directory、generic `credentials` / `credentials.toml` / `secrets.toml` 等をpathで拒否する。protected blobは原則として内容を読まない。

例外はrepository rootのtracked `.env.example` だけである。64KiB以下のUTF-8、NULなし、credential-like contentなし、assignment valueがすべて空であることを検証し、安全なtemplateだけをsnapshot実行treeから除外する。値入り、shell文、nested `.env.example`、変更対象としての `.env.example` は拒否する。

candidate mountは `snapshot` phaseだけに限定する。snapshot後のRED、offline、packet、broker、sign、judgeはcandidate repository pathを受け取らない。

verified physical snapshotは一般 `/artifacts` へcopyせず、host `snapshot-artifacts/{snapshots,red-snapshots}/<sha>/tree` からcoordinator専用read-only `/snapshots` mountへ渡す。PhaseResultのsemantic SHA集合とphysical directory集合をexact照合する。snapshot内の `AGENTS.md` を理由に一般artifact側のAGENTS/credential拒否policyを弱めない。

### 11.3 offline runner

RED/GREEN/gateはpinned runner imageで、read-only rootfsとsnapshot、`--network=none`、capability drop、`no_new_privileges`、非root user、限定tmpfs、PID/CPU/memory/time/output上限を使って実行する。home、Docker/Podman socket、agent、credential、host cacheをmountしない。

judgeはraw stdout/stderr digest、argv、exit、runtime probe、snapshot、時間を含む `OfflineRunEvidence` からGate/TDD evidenceを再構築する。candidateや人が作った要約値だけを信用しない。

通常pytestのcollection-time network guardと `live_api` marker + `--run-live-api` の二重opt-inは開発checkoutの補助防御として残す。これはsubprocess/native codeを止めるOS境界でも、外部送信・credential・課金の人間承認でもない。

### 11.4 review packetとbroker egress

review packetはtrusted diffと限定contextだけを含むtext-only canonical JSONである。credential path、secret-like assignment、provider token/private key/JWT、credential付きURI、NUL/binary、上限超過を拒否する。Responses inputの予約はprompt本文だけでなく、schemaとenvelopeを含むcanonical request JSON全体のUTF-8 byte数をtoken数の保守的上界として使い、260K hard limitと250K warningを適用する。

brokerはcandidate filesystem、mount、tool、shell、会話履歴を持たず、credentialはbroker processだけへ環境変数で注入する。gatewayはcredentialを持たず、固定 `api.openai.com:443` だけへTLS relayする。brokerは専用internal networkだけ、gatewayはそのinternal networkと専用external networkだけへ接続する。

role/attemptごとに一意なnetworkとgatewayを作り、raw runtime inspectからimage、network、mount、environment、credential不在、固定egress policyを検証する。実行後の再inspect、cleanup、container/networkのabsence確認までを1つの `ProvisionedBrokerExecutionEvidence` へ結ぶ。attested judgeはreviewerとadversaryのdistinct lifecycleを各1件要求する。

broker phaseはcanonical prepared batchだけをroot-owned outer executorへ渡し、raw outer evidenceをcoordinatorで再finalizeする。raw evidenceには両roleのprovisioned lifecycleと、失敗attemptを含むcanonical frozen final ledgerを入れる。host SQLiteのpath/device/inodeを単純copyやbind mountで後段証拠にせず、`prepared-payload.json` と `external-evidence.json` を `PhaseResult.external_execution_sha256` / `phase_sha256` へ結び付ける。同じallowlist/pricing policy bytesを使えばhost DB削除後もtyped evidence 2件を再構築でき、ledger改ざんは拒否される。

`reconstruct_attestation_inputs` はこのprepared/raw pair、immutable phase chain、dedicated snapshot、raw offline evidenceから、host SQLiteを削除した後もsign/judge共通のfrozen bundleを再構築する。`build_frozen_bundle_expectations` と `judge_frozen_attestation_bundle` はcanonical prepared/raw pairとpinned policy bytesからbroker evidenceを再finalizeするため、host ledgerやruntime再probeを権威入力にしない。sign/judgeは同じimmutable evidenceからrole別expectationを独立再構築する。raw SQLiteのcopy/bind mountは後段証拠として禁止する。

redirect、proxy、custom CA、credentialのargv/stdin/artifact混入、gatewayへのcredential、brokerのexternal network、host Codex直接実行は禁止する。

### 11.5 token・費用・attempt

requestはmodel=`gpt-5.6-sol`、`service_tier=default`、toolsなし、`store=false`、reviewer=`high`、adversary=`xhigh`、output最大12Kへ固定する。返却usageが予約inputを超える、またはoutputが12Kを超える場合は拒否する。

broker attemptは外部process起動前にcandidate外SQLite ledgerへtokenと費用を予約する。root-owned stdlib outerがO_EXCL・0600・STRICT schemaで新規作成し、既存ledgerを再利用しない。失敗、timeout、invalid responseでも予約を戻さない。roleごと最大2 attempt、標準packet 544K / 4.54 USD、絶対上限1,088K / 7.94 USDである。価格はcanonical pricing policy bytesとmanifest digestへ固定し、変更時は公式料金と新しいreleaseを人間が承認する。

### 11.6 署名、judge、人間承認

Ed25519 private keyはcandidate外の0400 fileとし、`sign` workflow prepareだけへread-only mountする。attested-judge workflow prepareだけがlauncher/coordinator所有の0700 nonce ledger rootをread-write `/nonce-ledger` mountとして受け取り、空またはexact contractに一致する0600 `nonces.sqlite3` だけを許す。task、policy、raw offline由来gate/TDD、reviewをruntime、snapshot、request、runner、argv、log、nonce、時刻へ結び付けて署名する。

nonce DBは `application_id=1095062094`、`user_version=1`、`journal_mode=DELETE`、`WITHOUT ROWID` の `used_nonces` tableとexact schema/index/table metadata、integrity、row domainを検査する。fileは0600 regular・link count 1・正しいowner・device/inode不変、directoryは0700でDB以外とWAL/journal/shmを拒否する。全署名のbinding・時刻・nonceを先に検証し、全nonceを単一 `BEGIN IMMEDIATE` transactionで予約する。重複、既使用、部分衝突は全件rollbackし、process再起動後もreplayを拒否する。

attested judgeは、raw offline evidence、reviewer/adversary各1件のdistinct provisioned broker lifecycle、失敗attemptを含むfrozen final ledger、全署名を再構築する。欠落、改ざん、別task/head/snapshot/runtime、重複session/lifecycle、期限切れ、replayはfail closedにする。host broker ledger削除後の `pass`、frozen evidence改ざん拒否、replay拒否は回帰テスト済みである。

phase順序はstdlib固定state machineでも再検証し、external launcherのouter `--workflow` entryとinner `prepare|finalize` CLIまで接続している。7/7 phaseがactual typed handlerを持ち、readiness gateは完全なhandler tupleをcredential FD読取り・broker ledger作成より前に確認する。generic `outer_descriptor_executor.py` はtest primitiveであり、provisioned broker production経路として認めない。outer entry、単一phase、library callbackを手作業でつないでlive運用を開始しない。

独立security reviewは7-phase重点回帰とnonce再監査を完了し、未修正CRITICAL/HIGHは0である。後続の実host検証でrootless Podman、trusted release、TaskSpec v2 canary、4 imageのcredential-free `nonlive_ready`、UID 1100所有のlive用initial requestまでは確認したが、Python 3.10 CI、live 7-phase workflow、API送信、課金実績を証明しない。

完全なprovenanceとcleanな通常判定では `pass` を返し得るが、全verdictは `human_approval_required=true` である。AIがcommit、push、merge、外部送信、credential利用、課金を自動承認しない。詳細は [統合済みAIレビュー規約](DEVELOPMENT.md#統合済みaiレビュー規約) と [HARNESS-RUNBOOK.md](HARNESS-RUNBOOK.md) を参照する。

## 12. 本番公開前の残作業

次は現行機能ではなく、実装と検証が必要な事項である。

- 認証、認可、利用者別・テナント別データ分離
- API利用量・費用の観測と異常通知。現行local productionではquotaとレート制限を設けず、公開・複数利用者化する場合だけ濫用対策を再検討する
- local job境界と実検索・利用者操作の接続、複数process運用、強制停止可能な実行隔離
- 構造化ログ、相関ID、監査ログ、メトリクス、アラート
- シークレットとキャッシュの保持・削除方針
- 外部商品URL・画像URLの検証方針
- 複数ワーカーで安全な保存方式
- AIハーネスのnonce ledger保持・backup・容量・rotation、古いattestationの検証方針、live 7-phase workflowに対するcredential・費用・送信内容の運用承認

これらの大規模対応は [大規模タスク一覧](GOAL.md#統合済み大規模タスク一覧)、現行構造に残る負債は [技術的負債トラッカー](ISSUES.md#統合済み技術的負債トラッカー) で管理する。

## 13. Bonsai正本の商品検索フローの安全境界（基盤を一部実装）

[SEARCH-FLOW.md](../SEARCH-FLOW.md) の利用者フローを実装するバックエンドでは、次を必須にする。

2026-09-08に採用した先行参考画像の確認では、1枚の生成成功を後続生成の承認とみなさない。先行画像と現在の条件、owner・sessionへ結び付いた明示了承の後だけ、別の予約で条件別偽画像だけを生成する。同じ了承は後続生成1回に限り、画像の作り直し・条件変更・期限切れ後の利用と二重利用を拒否する。偽画像の生成終了もOutscraperの最終承認を代替しない。旧経路の一括生成・確認の実績は、この新しい境界の検証として扱わない。

`src/search_v2/` では型coercion、未知field、nestedの検証済みinstance偽装、価格mode矛盾、入力・query上限、control文字、URLをfail closedにする。`bonsai_request.py` は固定v2 promptだけをschema 8.0のsystem messageへ入れ、非空のbounded compact生成schemaを `response_format.schema` へ含め、source・prompt・完全schema・生成schema・body・model・endpoint・response上限をdomain-separated v8 digestへ結ぶ。完全canonical schema本文はmodelへ二重送信しないが、別digestとapplication側のstrict最終検証には維持する。application output-token上限とHTTP timeoutは公開契約に持たず、request byte数と最大response byte数を保守的なledger予約値にする。requestに一致するreserved Bonsai intent 1 callを開始して注入transportを1回だけ呼び、成功・失敗を同一process ledgerへ確定する。`bonsai_http.py` は新規Requests Sessionを1 attemptだけ所有し、`trust_env=False`、既定metadata除去、TLS検証、retry 0、redirect禁止、streaming 1 MiB上限を固定する。timeout optionは指定せず、応答、接続・OS失敗、server context境界、EOS、または人間の手動停止まで待ち得る。非200、不正content type、圧縮、宣言済み上限超過のbodyは読まず、ResponseとSessionを常に閉じる。`bonsai_adapter.py` はfull raw response body、exact prompt、完全canonical schemaを受け、OpenAI互換envelopeとcontent全体の単一JSON objectをstrict検証する。検索可能compact wireは最大12種類の固定field、確認待ちは `ambiguities` 1 fieldだけを許し、商品名等48文字、term 32文字、各term list・typed condition・set値4件、ambiguity 2件・各96文字へ制限する。categoryはproduct nameへ、colorとfeaturesはtermsまたはtyped conditionへ集約し、省略値を完全19-field draftへ決定的に補完して再検証した後、normalizerへ渡す。非blocking intentは既存query plannerで検索queryを構築できる場合だけ受理し、正規化失敗は `intent_normalization_invalid`、検索不能なresponseは `intent_searchability_invalid` へ写像する。blocking ambiguityはquery planなしで受理し、評価用のquery-less blocking投影を維持する。不一致は固定messageと本文非保持の段階診断へ変換する。現行の生成用schemaは、ambiguity code regex、同値のllama.cpp互換decimal regex、価格mode・source別8 sparse variant、固定field branch、文字列・配列上限に加え、通常経路の商品種別または1件以上の全blocking ambiguityを生成時に強制し、完全schemaとquery plannerを最終権威として維持する。draft schema不一致時はPydantic error locationだけから固定groupを導き、検索不能時は正規化済み検索fieldの有無だけから `missing_terms` または `invalid_terms` を導く。どちらも値、message、input、contextを保持しない。`tokenizer.py` はNFKC後のURL、改行、control文字をtoken抽出前に拒否し、URL記号を除去して通常語へ救済しない。本文ではなく各artifactのSHA-256をserializable modelへ保持し、生入力、prompt、request body、response、Pydantic入力値を利用者向け例外へ含めない。health-readyなrequest v5は使用済み4件でstrict intent検証まで成功し、EXEC-053の先頭1件は生成時検索可能性schemaからtyped proposal生成まで成功して `blocking` となった。request v6は初期の出力1 token benchmarkに加え、EXEC-058でfull JSON・strict intent・cache hit、EXEC-059で同一487 completion tokensのprompt・生成時間分離までlocalhost確認した。warm時は923 / 924 prompt tokensをcacheしてprompt処理353.47倍・wall全体1.52倍となり、wallの99.82%をcompletion生成が占めた。request v8の代表compact JSONはoffline tokenizerで104 tokensだが、実生成・品質・速度は未確認である。意味品質、blocking判断の妥当性、typed ranking、Core Ultra性能、production成功は未確認である。このpackageは現行 `run_product_search()` へ未接続である。

後続の明示承認済みrequest v7 localhost診断は、応答未完了の365.12秒時点で利用者指示により手動停止した。
停止直前はserver内の生成が進行中で、clientはsocket read待ちだった。生response、server log、cacheは保存せず、
停止後はserver processなし・port非listenを確認した。完了call数、completion token数、strict結果、速度、
品質は確定していない。

`search_job.py` はlocal単独利用を前提にownerを `local-user` へ固定し、job DBへbinding digest、状態、時刻、固定失敗code、結果locatorだけを保存する。検索文、商品、画像、approval token、provider要求・応答・URL、credential、callback、例外本文は保存しない。同じbindingの再投入は既存jobを返し、別callbackを開始しない。DB fileは新規0600、regular file、既知schema、canonical row digestを要求する。

`production_search.py` は最終承認済み検索と同じowner・session・元入力に結ばれた承認済み参照をjob bindingへ固定し、worker内でだけcredential loaderを呼ぶ。Outscraper 1 task、商品画像、固定CLIP、ranking v5、schema 5.0履歴を順に実行し、jobには成功履歴locatorだけを返す。同じbindingの再投入、取消・失敗後の自動再実行を行わない。fixture E2Eはこの保存境界を確認するが、実provider、API、browser、認証済み利用者分離を証明しない。

running jobの取消は協調方式であり、in-process callbackまたはその内部で待機中の通信をthreadから強制停止しない。callbackは外部stageへ進む前に `SearchJobControl` を確認し、取消後に返した結果もexecutorが成功として採用しない。process再起動時はcallbackを復元・自動retryせずactive jobを固定終端へ移す。この境界は単一executor・単一processだけを対象とし、同じDBへ複数executorを接続する運用、公開API、認証・認可の代替には使わない。

EXEC-051で生成用schemaを11,051 bytes・SHA-256 `c8537ff3ee378b0ef57d41889210e1a807962d2cbd1ab8772020706481a58ca6` へ置き換えた。EXEC-052後は通常の商品種別または全blocking確認待ちを必須とする16,663 bytes・SHA-256 `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d` のschemaへ更新した。完全schemaからpatternを除く旧説明は履歴であり、現行は互換regex、価格9 variant、生成時検索可能性を強制する。draft不一致と検索不能の安全診断は固定groupだけを追加し、生値やPydantic validation本文を保持しない。

EXEC-053では、この16,663 bytesのschemaを使用済みCSVの先頭1件・合計1 callだけへ適用した。HTTP 200後にstrict intentとtyped proposal生成まで成功し、proposalは `blocking` となった。検索文、生response、正規化intent、typed condition、ambiguity、issue本文は保存しておらず、blocking理由を事後推定しない。2件目、retry、assessment、商品取得、rankingはなく、server・port・process・一時runnerを片付けた。後続のEXEC-054で追加model callを行わず、query-less blockingを専用第1確認へ返し、Cloudflare・Outscraperの予約・callより前に停止するoffline境界を実装した。新しいsession bindingと固定errorにも検索文、ambiguity message、商品情報、provider本文を複製しない。

EXEC-055では、同じ使用済みCSVの先頭1件を現行orchestratorへ合計1 callだけ通した。`/health=200` 後のHTTP 200・2,508 bytesをstrict処理し、typed status `blocking`、query plan・query digestなしの `BlockingIntentReview`、Bonsai利用量 `succeeded` へ到達した。検索文、生response、正規化intent、typed condition、ambiguity・issue本文は保存せず、2件目、retry、assessment、商品取得、ranking、Cloudflare・Outscraperの予約・callを実行していない。loopback以外のnetwork、credential、費用はなく、server停止後にport・process・一時runnerの不在を確認した。SHA-256は匿名化として扱わず、この1件を独立holdoutまたはproduction成功の証拠にしない。

`approval.py` はowner・session・intent・query・Outscraper request・任意画像・provider allowance・runtime digest・15分期限をcanonical planへ結び、`state_machine.py` はraw tokenを返却時以外に保持せずdomain-separated SHA-256で照合する。同一process内の消費ledgerは並行した二重claimを一つだけ成功させる。計画変更、stale revision、期限切れ、owner・session・plan・token不一致、再利用、承認発行より前に開始したOutscraper予約をfail closedにする。

`usage_ledger.py` はcallerが予約時刻を指定できない契約にし、server側UTC時刻でBonsai・Cloudflare・Outscraperのcall・token・整数micro-USDを送信前予約する。未開始予約だけを解放し、開始済みの成功・失敗はどちらも上限へ残す。pricing policyと利用policy digestの不一致、snapshot改ざん、集計上限超過を拒否する。ただし両ledgerはin-memoryかつ同一process内だけがatomicである。将来のAPIはbrowserから任意snapshot、承認済みflag、予約状態を受け取らず、server-sideのtransactional repositoryを正とするまで複数workerへ公開しない。

`cloudflare_request.py` はaccount ID、API token、Authorization、endpointを入力またはmodel fieldに持たない。生成promptは正規化済みintentのうち商品種別、カテゴリ、色、必須条件、見た目の特徴だけを属性dataとして含め、source input全文、価格、negative・preferred term、brand、model numberを含めない。参照PNGは8 MiB以下、chunk・CRC整合、縦横511px以下を検証し、実行時bodyをserializable metadataから除外してSHA-256、長さ、寸法だけを残す。

`cloudflare_http.py` は開始済みのexact 4-call予約と `image_generating` stateを同じledger内で照合してからだけ、server-side account IDとAPI tokenを使う。Requests Sessionは環境proxy、`.netrc`、環境CA、既定header、cookie、authを継承せず、TLS検証、retry 0、redirect禁止、streaming上限を固定する。HTTP 200、JSON content type、identity encoding、宣言・実測4 MiB、UTF-8、duplicate key、非有限数、exact envelope、canonical Base64を検証する。decode画像は2 MiB以下のJPEG・PNG・WebPだけをmagicとPillow formatで受理し、完全decode・単一frame・512×512を確認してmetadataなしRGB PNGへ正規化する。旧先行確認付き4方向経路は4要求とも了承済み先行画像の511px参照を使い、旧低位経路は基準の512px PNGから派生3要求の参照を作る。4枚がそろった場合だけ `image_review` stateを返す。1枚でも失敗した場合は部分画像を返さず予約を `failed` にし、`state_machine.py` と `orchestrator.py` が失敗reservation IDを `image_generation_failed` と `ImageFailureReview` へ結ぶ。API token、生provider文、任意header、raw response、画像bodyはserialized artifact・state・固定例外へ含めず、失敗attemptも利用上限へ残す。これはmock・合成画像によるoffline境界であり、形式正規化修正後の実Cloudflare応答shape、生成品質、永続保存、browser公開を証明しない。

`outscraper_request.py` はAPI key、`X-API-KEY`、Authorizationを受け取らず、1回のGETへ最大2件の反復 `query` と固定domain・language・24件/query・`async=true`、検証済みendpoint・server-side postal codeだけを持つ。queryとpostal codeはreprへ出さず、request digestには含める。guardはactual query batch、query plan digest、request digestをapproval token claimより前に照合し、不一致時はtokenを消費しない。照合後もowner・session・期限、single-use token、承認発行後に開始した1-call予約を既存state machineで検証する。返すpermitはcredentialを持たず、HTTP送信またはprovider成功を証明しない。

`outscraper_http.py` はそのpermitと同じledger内の開始済み予約を再検証してからだけAPI keyを注入する。task作成とpollはそれぞれ隔離したRequests Sessionを使い、same originかつ初回IDに一致する結果path以外へcredentialを送らない。応答はJSON content type、identity encoding、宣言値と実測値の8 MiB上限、UTF-8、duplicate key、非有限数、official status、最大48候補を検証する。成功時は限定した `data` とprovider request IDだけを返し、失敗時は生応答を保持せず利用量予約をfailedへ確定する。

`product_pipeline.py` は成功済みexecution、schema 3.0の承認plan・session、intent、query plan、ready proposal、request、利用量、typed ranking・product evidence profileの結合を再検証してから、観測値だけの正規化と画像無効の `typed-ranking-v4` へ渡す。sessionへ残すのは件数、typed batch digest、正常結果種別、失敗工程・固定コードだけであり、生provider応答、query、postal code、商品本文、URL、生例外文は保持しない。このoffline・mock検証は実送信、課金、実provider品質、検索順位品質、永続化、API・UIを証明しない。

`orchestrator.py` はBonsai実行後のtyped proposal付き第1確認、任意の先行画像の了承、参考画像と後続偽画像の確認、Outscraper前の最終確認を別stageとして返し、自動通過させない。blocking proposalは画像生成、画像なし続行、最終承認、Outscraperより前に止める。Bonsai request・利用量、typed proposal、任意のCloudflare image set・利用量、Outscraper request、normalization・typed ranking・product evidence profile、実装・利用policyをdomain-separated runtime digestと承認planへ結ぶ。画像途中失敗後は固定回復stageで停止し、利用者が別操作で選ぶまでproviderを呼ばない。明示retryは先行1枚を最大2回の範囲で作り直し、新しい了承後だけ偽画像を生成する。過去後続の成功・失敗分もCloudflare allowanceへ算入し、同じ了承を再利用しない。画像なし続行と生成画像の破棄は最終planから画像bindingを外すが、開始済みCloudflare利用量をledgerから消さない。承認発行だけではOutscraperを呼ばず、その後に作成した開始済み予約とexact requestが一致する場合だけsingle-use tokenをconsumeする。stage、state、resultはcredential、生provider応答、raw tokenを保存せず、`ApprovedSearch` はreprを無効にする。現在は同一processのoffline境界であり、永続transaction、実provider、API・browser接続を保証しない。

`history_snapshot.py` は正常完了result、承認済みreview、元入力のowner・session・intent・query・typed proposal・承認plan・typed batch・任意画像を保存前に再検証する。条件decisionは必須状態と「一致」「未確認」「情報が矛盾」「不一致」等の限定表示へ変換し、元入力はexact digest照合後だけ表示用に正規化する。raw score、component、weight、evidence、registry、採用言語、provider、model、request ID、postal code、token、利用量、digestを商品表示snapshotへ入れない。`history_repository.py` はschema 2.0のstrictな保存入力とbrowser向けallowlist相当の一覧・詳細・参考画像modelを分け、全操作でownerを必須にする。詳細・画像・個別削除はowner不一致、不在、期限切れを同じ固定not-foundへ変換し、内部 `history_id`、completion key、ownerを返さない。履歴と専有512px PNGをSQLite `user_version=2` のforeign keyと単一transactionで保存・削除し、30日到達後はcleanup前でも読取から除外する。旧version 1 DBはbyteを変更せず拒否する。新規DB fileはPOSIXで0600とし、未知のschema version、必須table・columnの欠落、group・other権限を持つ既存file、表示JSONと保存SHA-256の不一致を固定storage errorで拒否する。ただしownerは認証済み主体から解決せず、同じOS userでfileを共有する。複数worker、backup、at-rest暗号化、scheduler、legacy現行pipelineからの保存呼出し、API・browser接続も保証しない。

`holdout_evaluation.py` はprovider client、file reader、画像runtime、動的import、callbackを持たない。予測builderは完全なintent、query plan、typed proposal、ranked batchを一時的な入力として再検証するが、serializableな予測setへはartifact digest、条件identity、商品digest、decision状態、必須状態、順位だけを投影する。正解datasetもrepository用ID、非個人のprovenance reference ID、source input digest、canonical条件、商品digest、labelだけを保持し、利用者の検索文、商品名・説明・ASIN、URL、画像byte、生provider応答、生例外、元Excel metadataを入れない。公開評価入口はdataset・prediction・profileの不一致を生入力のない固定errorへ変換する。これは保存先の暗号化、label秘匿、blind評価、データが本当に未使用だったことの証明を提供しないため、実holdoutの出所・分割・アクセス権・保持期限は別の人間管理を必要とする。

`holdout_acceptance.py` もprovider client、file reader、画像runtime、動的import、callbackを持たず、再検証した評価reportだけを受ける。serializableなassessmentはpolicy・report・dataset・prediction・profileのdigestと、固定metric名、scope、category、限定された件数・比率、比較結果だけを保持し、report本文や正解label本文を複製しない。元reportの `quality_decision=not_assessed` を変更せず、別artifactの `pass` も外部通信、production E2E、画像ranking、commit、push、人間承認を許可しない。SHA-256は匿名化ではないため、source input digestを含むholdoutには非機密dataだけを使う。

`holdout_postprocess.py` もnetwork、file reader、動的import、callbackを持たず、strict intent後の評価処理をtyped proposal、query plan、typed ranking、prediction projectionの固定4段階へ写像する。失敗時に公開するのは列挙済みstageと固定messageだけで、検索文、商品情報、provider応答、URL、ASIN相当値、元例外の型・本文・cause・contextを保持しない。上流blocking ambiguityはquery plannerを呼ばず、intent・proposal digestだけを持つquery-less blocking predictionへ投影するため、検索前停止を失敗へ潰したり評価目的のquery生成で回避したりしない。これは今後の再計測を安全に分類する境界であり、過去に保存しなかった本文や失敗段階の復元、実provider成功、production E2Eを証明しない。

EXEC-042のlocalhost Bonsai評価では、検索文は固定prompt・schemaとともにlocal modelへだけ渡し、商品名、構造化商品情報、URL、ASIN相当値はモデルへ送らなかった。server logとprompt cacheを無効にし、生responseを保存せず、結果にはdigest、固定status、件数、metric、checkだけを残してserverを停止した。EXEC-043では本文を保存せず不適合段階を識別できるようにし、利用者承認後に同じCSVをlocalhostだけ、4 calls、retry 0、各300秒、credential・費用なし、ログ・cacheなしで再送した。4件全てが旧application timeoutで `request_failed` となり、parserへ到達しなかった。EXEC-044で生成token上限とHTTP timeoutを削除し、EXEC-045では無期限待機、手動停止、保存範囲を再提示して別の明示承認を得た。同じ4件は全てHTTP完了後に `content_not_json` となった。生responseは保持せず、server停止、port非listen、process終了を確認した。結果はdevelopment regressionとしてだけ記録する。

EXEC-048後の段階診断付き再計測では、完了2件がstrict intent後の `query_plan_invalid` となった。利用者の実行数訂正時に送信済みだった3件目を手動中断し、4件目は送信していない。部分実行からdataset assessmentを作らず、生response・正規化intent・検索文・商品情報・内部例外本文も保存していない。訂正後の追加model callは行っていない。EXEC-049後は更新prompt、localhost endpoint、全体1 case・1 call、retry 0、credential・費用・外部networkなし、本文非保持を再提示して新しい明示承認を得た。先頭1件はHTTP 200後の `intent_normalization_invalid` で受理前に停止し、2件目、retry、dataset assessmentは実行していない。承認済み上限の1 callは消費済みである。実行時点ではnormalizerと検索可能性検査が同じstageだったため、追加推論なしで検索不能を `intent_searchability_invalid` へ分離した。両stageとも元例外のcause・contextを残さない。次のmodel callには、同じcaseでも再度の明示承認が必要である。

EXEC-051では同じ境界を再提示して新しい承認を得た後、旧生成schemaの先頭1件を1 callだけ送った。HTTP 200後に `draft_schema_invalid` となり、2件目、retry、assessmentは行わなかった。検索文、生response、正規化intent、商品情報、validation本文は保存していない。今回の直接違反groupは旧diagnosticから復元せず、追加推論なしで生成schemaと固定group診断を改善した。新schemaの実model確認には別の明示承認が必要である。server停止、port非listen、process終了、一時runner削除を確認した。

EXEC-052では更新した条件を再提示して新しい承認を得た後、EXEC-051の生成schemaで先頭1件を1 callだけ送った。HTTP 200後、生成schema、完全draft schema、正規化を通過して `intent_searchability_invalid` となった。2件目、retry、assessmentは行わず、検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、validation本文を保存していない。実行時点に検索可能性groupはなかったため過去responseを事後分類せず、追加推論なしで商品種別またはblocking確認待ちを強制する次schemaと固定group診断を実装した。次schemaの実model確認には別の明示承認が必要である。server停止、port非listen、process終了、一時runner削除を確認した。

`product_normalization.py` は検証済みOutscraper request descriptor、provider request ID、明示的な換算profileとprovider応答だけを受け取り、intent、prompt、client、callbackを受け取らない。最大候補数とraw文字列・数値文字列・配列の処理量を正規化前に制限し、strict出力、固定エラー・reject理由、request・query・profile・batch digestへ投影する。商品title、description等の命令風文字列もデータとして扱い、属性補完やBonsai・OpenAIその他のLLM呼出しへ接続しない。商品URLはAmazon.co.jpのHTTPSへ限定し、画像URLはHTTPS・構文・長さまで検証して後続の `image_proxy.py` へ渡す。provider request IDとdigestは内部provenanceであり、browser向けmodelではallowlistから除外する。このnormalizer単独は明示承認、HTTP成功、実サービス応答を証明しない。

`image_proxy.py` は実network clientを内蔵せず、server-side exact host allowlistと注入するresolver・transportを必須にする。userinfo、IP literal、非443 port、fragment、非HTTPSをDNS前に拒否し、resolverが選んだ最大8件の解決結果を全てglobal IPへ限定する。transportには解決済みIP、redirect禁止、10秒、identity encoding、8 MiBを渡し、返された実peer IPを解決結果へ照合する。宣言・実読込byte数、MIME、magic、JPEG・PNG・WebP、単一frame、縦横4096px、総pixel数、decompression bomb warningを検証し、metadataを除いたRGBとdomain-separated digestだけを内部artifactに残す。URL、raw response、RGB byteは通常のserialized modelと固定例外へ含めない。

`image_proxy_dns.py` は小文字ASCIIのcanonical DNS hostだけを受け、443番のTCP用IPv4・IPv6を `getaddrinfo` 1回で解決する。生結果は最大64件に制限し、上限内の全項目について組込みlistとexact tuple構造、family、socket type、protocol、空canonical name、port、IPv6 flowinfo・scope ID、canonical numeric addressを検証する。検証後に結果順を保って重複排除し、transportとprocess IPCへ渡す候補を最大8件に制限する。選択した全候補のprivate、loopback、link-local等のglobal判定は直後のcoreで行い、空・過剰・不正結果や生resolver例外は固定messageで拒否する。

`image_proxy_dns_process.py` はWindows 11 / WSLで共通利用できる明示的な `spawn` により、上記resolverを要求ごとのdaemon子processへ隔離する。親processはprocess準備前から5秒のapplication deadlineを計測し、結果待機を4.5秒で止め、terminateとkill後のjoinを各最大0.25秒へ限定する。子processは成功時のcanonical numeric addressだけを最大512 bytesのASCIIへencodeし、失敗時は固定tagだけを送る。親processはpickle objectを受け取らず、byte数、tag、件数、ASCII、canonical IPv4・IPv6を再検証してから既存coreへ渡す。timeout、異常終了、EOF、malformed IPC、close失敗はhost、IP、生例外を含まない固定errorにする。親でのKeyboardInterrupt等は子process回収後に再送出し、停止操作を握りつぶさない。これはsandbox、権限分離、DNS真正性を提供せず、Pythonの `Process.start()` 自体をpreemptできない。fake process・pipe・clockとWSL2の外部DNSなし固定失敗smokeまでを確認し、Windows native・実hostは未確認である。

`image_proxy_http.py` はこのtransport契約を再検証し、許可済みhostを通常のHTTP clientへ渡して再解決させず、検証済み一覧の先頭numeric IPへIPv4またはIPv6 socketで1回だけ接続する。元host名はTLS SNIと証明書検証へだけ使い、certificate required、hostname check、TLS 1.2以上、HTTP/1.1 ALPN、TLS compression禁止を固定する。接続後のpeer IPが選択IPと一致してから、origin-form GET、Host、画像MIMEのAccept、identity encoding、connection closeだけを送る。redirect・非200・不許可MIME・HTTP圧縮・宣言済み上限超過のbodyは読まず、曖昧なframingと上限超過streamを固定errorにして、response・TLS・raw socketを全経路で閉じる。別IPへのfailoverとretryは行わず、実host通信は未確認である。

`image_proxy_service.py` は1〜32件のcanonical host allowlistをconstructorで固定し、省略時にprocess分離resolverと上記transportを各1回構築して既存coreへ渡す。公開取得methodはURLだけを受け、request単位でpolicy、allowlist、resolver、transport、timeout、byte上限を差し替えられない。service自身はnetwork client、retry、failover、redirect、cache、credential、logを持たず、設定不正を `image proxy configuration is invalid`、取得経路の全失敗を `image proxy request failed` へ変換する。serviceと固定設定は合成host・注入fixtureだけで検証しており、運用allowlist値、実DNS・TCP・TLS・HTTP、Windows nativeでのprocess動作は未確認である。

`image_similarity.py` はpHash/Hamming距離を閾値5以下の重複判定にだけ使う。意味的scoreは固定CLIP runtime digestへ結んだ512次元・有限・L2正規化済みembeddingだけを受け、4方向ごとの最大cosine平均から作る。model名によるdownloadを行わず、repository-local asset rootの `config.json`、`model.onnx`、`preprocessor_config.json` だけを許可し、symlink・hardlink、byte数、SHA-256、読込中のfile identity変化を拒否する。

画像scoreは色、外観形状、商品種別など画像で確認できる特徴だけの補助評価とし、商品仕様を表す構造化属性の推定、補完、上書きに使わない。有線・無線は商品名とproviderから得た構造化された観測属性で判定し、画像scoreでhard filterしない。画像生成物と高い類似scoreは、実商品仕様の証拠として扱わない。

`image_similarity_onnx.py` は最大4枚の検証済みRGBをBICUBICで縦横比を維持したまま224×224内へ収めて中央配置し、残りをCLIP image meanで埋める。余白は固定mean・stdによる正規化後0となり、NCHW `float32`へ変換する。application preprocessing profile IDをruntime digestへ含め、旧center-crop embeddingとの混在を拒否する。ONNX Runtime 1.23.2のactive providerを `CPUExecutionProvider` だけに固定し、thread数、sequential execution、graph入出力名・型・shape、512次元output、有限・非0を検証する。asset全体をsession作成前と推論後に再検証し、生ONNX例外とpathを固定errorへ変換する。PyTorch、Transformers、pickle weight、model resolver、runtime download、provider fallbackは使わない。

`image_similarity_process.py` は親で作った最大約2.4 MBの固定tensor bytesだけを、明示的な `spawn` 子processへ渡す。子からは最大約8 KBのlittle-endian `float32` embedding bytesまたは固定失敗tagだけを受け、30秒のapplication deadline内に終了しない場合はterminate、なお生存時はkillする。constructor、provider、thread数、deadline、IPC上限をrequestから変更できず、自動retryもしない。process isolationは別OS user、filesystem sandbox、network namespaceではなく、Pythonから `Process.start()` 自体をpreemptできない。受領1組は正例自身を参照にした3回の最小識別smokeで同じembeddingと期待順序を確認したが、固定assetのONNX parser安全性、Windows native、複数query・4方向参照・複数商品によるranking品質、Git配布は未確認であり、画像rankingは無効のままにする。

[EXEC-065](GOAL.md#exec-065-未知の視覚条件に対する条件別counterfactual画像評価) の実験境界では、未知の視覚語句を既存SudachiPy/英数字tokenizerでNFKC/casefold済み元入力spanへ再照合し、最大3件に制限する。`counterfactual_image.py` はsource・registry digest、local condition ID、順序、referenceのpixel digest・pHash非重複、固定CLIP runtimeを再検証し、外部network、provider、ML runtimeをimportしない。source spanを復元できない語を生成promptへ送らず、LLMへcondition ID、evaluator、model、path、URL、weight、閾値を選ばせない。4件以上は自動選択せず、画像生成前の利用者選択または画像なし続行を要求する。数値寸法、個数、互換性、接続方式、容量、性能、材質など画像だけで確定できない条件をcounterfactual評価へ入れない。

確認済みsource phraseも非信頼入力である。実装済みdomainは32文字上限、URL・改行・control文字拒否を再適用する。生成境界では固定templateのデータ位置にだけ入れ、required・preferredでは対象外観の除去、excludedでは対象外観の追加という固定operationだけを許可し、自由形式の反対語、追加命令、negative prompt、model parameterを利用者入力、Bonsai応答、商品dataから受け取らない。minimum-positive v4のbatch較正は条件名・category・正解labelを受け取らず、同じbindingの完全な4〜32候補だけを扱う。候補不足、digest混在、重複候補、観測幅不足、ゼロを跨がず飽和端点の複数支持もない片側分布を拒否し、calibrated marginを作らない。共通閾値0はdevelopment相対合格に限り、独立holdout未実施かつranking無効である。数値的に分離しない参照を `unknown`、候補欠損を `missing` にする。

実験referenceはdesired anchor 1枚と、条件ごとに1要素だけ違反させた最大3枚である。候補画像と候補embeddingはlocal境界から出さず、Cloudflareまたはテスト用gpt-imageへ送らない。期待する `1 + N` 画像の欠損、pHash重複、条件以外の大きな変化、意味逆転、参照embedding分離不足はset全体をfail closedにし、部分採用や自動retryをしない。開始済みcallは失敗時もledgerへ残す。raw prompt、利用者入力、候補画像、商品識別子、生provider応答をartifact、log、例外、履歴へ保存しない。

development較正では、実行直前に送信範囲を提示して明示承認を得たうえで、組込みgpt-imageへ電気ケトル2 callsとオフィスチェア4 callsの合計6 callsだけを送り、retryと自動再実行は0だった。候補商品画像、候補embedding、商品URL、商品識別子、API credentialは送信していない。生成credentialを取得・表示せず、生provider応答とraw promptをrepositoryへ保存していない。保存対象は利用者確認済みの参照PNG、非機密manifest、集計済み較正結果だけで、本番Cloudflareと製品経路は呼んでいない。

v4 scoreは、条件i以外のcounterfactualが条件iを維持するという人間確認済みreference契約だけから正例集合を作り、最低cosineを使って全正例との一致を要求する。条件名、類似語辞書、候補集合、他候補score、labelを1候補の計算へ入力せず、候補画像と参照画像のpixel digest同一、固定runtime不一致、condition/reference binding不一致を拒否する。相対選択はlocalの集計値だけを扱い、外部service、画像、商品data、credentialを受け取らない。同一dataset・label・評価contract digestと件数が一致しない比較を拒否し、比較対象やlabelの差し替えによる見かけ上の改善を合格に使わない。今回の相対合格は独立holdoutへの進行可否だけで、ranking有効化、Cloudflare呼出、製品仕様変更、外部送信を許可しない。

暫定productionの公開入口は、元入力とintentのsource SHA、再構築したcounterfactual condition setを照合して先行1枚だけ生成する。先行確認はledger別process-local registryとlockで管理し、15分期限、最新画像、owner・session、policy・利用量bindingを後続要求前に照合する。明示了承後は偽画像N callsだけを別予約で生成し、全成功後だけ専用0600 SQLiteへ生成物確認のdigest、owner・session、15分期限、消費時刻を保存する。raw tokenと画像bodyは保存しない。SQLite承認consumeは原子的single-useで、owner・session・condition・reference・request・usage bindingの変更、期限切れ、token不一致、再利用をlocal参照変換より前に拒否する。先行確認のregistryはDBへ永続化せず、再起動後に復元しない。schema 5.0履歴は既存desired＋counterfactualの保存形式を維持し、後続4方向を追加保存しない。商品画像URLとembeddingは保存せず、履歴record削除時に生成参照BLOBをcascade削除する。

固定合成基準画像1枚と、旧低位adapterを使う固定合成1条件のdesired＋counterfactual最小setは、それぞれ別承認の実Cloudflareで生成・正規化保存まで成功した。後者はexact 2 calls、retry 0、全成功時だけの0600出力、安全な固定診断を実測し、対象条件だけを反転した画像内容も定性的に確認した。この実績は先行1枚の確認と4方向を含む新公開入口のlive検証ではなく、未知条件全般、実請求、API、UI、production E2Eの成功も示さない。

実商品画像proxy・固定CLIP専用runnerは、商品画像URLを通常設定やargvへ追加せず、live時だけ `SecretStr` のtest専用設定から読む。URLはexact `m.media-amazon.com` のHTTPSだけを許可し、既存proxyのDNS・pinned-IP TLS・10秒・8 MiB・redirect/encoding拒否を変更できない。既存の0700 directoryから0600・単一link・所有者一致・exact 2 filesだけを読み、画像契約と読込中のfile identityを再検証する。出力は新規absolute PNGへ0600でexclusive作成し、URL、生response、header、IP、embeddingをresult・例外・保存画像へ含めない。fixture成功は実host通信を証明せず、liveは別承認まで実行しない。

商品画像URL取得は別承認後、fresh 0700 profileのheadless ChromiumでAmazon.co.jp検索結果へ1 navigationだけ行った。CDP送信前interceptionは外部要求100件だけをcontinueし、追加65件を送信前に遮断した。retry、詳細ページ、login、既存Cookie、画像保存は行わず、exact hostのURL 1件だけを0600・Git除外の `.env` へ値非表示で原子的に保存した。URL、生DOM、商品名、ASIN、Cookie、生responseはstdout・文書・artifactへ保存せず、browser profileと一時runnerを削除した。この取得成功は画像GET、decode、CLIP、rankingの成功を示さない。

続く限定liveは、Outscraper本番統合でないことを明示して改めて承認を得た後、保存済みURLへproduction proxyで1 GETだけ行った。retry・redirect・別IP failoverなし、DNS 5秒application deadline、HTTPS 10秒・8 MiB、固定local CLIP 30秒を維持し、1 GET・retry 0・CLIP 3画像で成功した。結果にはURL、生response、header、IP、embeddingを含めず、候補は新規0600 PNGへ保存した。これは実hostへの安全な取得とlocal推論の確認であり、Outscraper credential、商品task、複数候補、rankingを使用していない。

Outscraper商品画像から暫定ranking v5までの統合backendは、成功済みの1-task利用予約、日本語query 1件・最大24候補、消費済み人間承認へ結ばれたcounterfactual参照だけを受理する。商品ごとの先頭画像URLは既存proxyのallowlist・DNS・pinned-IP TLS・10秒・8 MiB・redirect/retry禁止を変更せず使い、取得失敗または画像重複をmissing、有効候補4件未満をunknownにする。安全な集計にはtask・poll・候補・画像要求・画像状態の件数だけを含め、Outscraper API key、生response、provider request ID、商品本文・識別子、商品・画像URL、画像byte、embedding、生例外を含めない。保存済みPNGだけからCloudflare request metadataまたはapproval receiptを捏造する経路はない。現時点の確認は外部通信なしのfixture・mockであり、live実行には別の条件提示と明示承認を必要とする。

対話式live runnerはCloudflare execution、request metadata、生成画像body、raw approval tokenを同一processの非表示stateにだけ保持する。目視用PNGは新規0700 directoryへ0600・単一linkで保存し、保存時のdirectoryとfile identity、mode、長さ、digest、byte内容を承認consume直前に同一file descriptorで再検証する。SQLiteへはdomain-separated token digestとbinding、期限、consume時刻だけを保存する。参照fileの置換・改ざん、15分期限切れ、token不一致、二重consumeではOutscraper設定loaderより前に固定stageで停止する。承認後もOutscraper taskは1回、retry 0、候補24件、商品画像GET 24回、CLIP 7 batchesが上限であり、provider失敗後に自動再実行しない。call数は強制するが金額上限は設定しないため、実live前の最新単価による見積り確認は省略できない。初回liveはCloudflare 2 callsとOutscraper 1 task後にranking段階で失敗し、再実行していない。後続の安全診断はclosedなsubstageと非負件数または未到達の `null` だけを階層間で伝搬し、生例外、商品data、provider ID、URL、画像digest、score、embeddingを保存・表示しない。fixtureによる診断確認は初回liveの原因特定または実サービス成功を示さない。

batch較正はcandidate scoreの最小値・最大値に依存するため、candidate digestの順序と一意性を結果へbindingし、正解label、商品本文、source phraseを較正入力へ含めない。単一classを常に検出できるとは証明していないため、分布の安全弁を通過してもproduction decisionまたはrankingへ昇格させない。outlier混入、候補構成変化、未知categoryでの精度は独立holdoutで評価する。

固定ONNX graphにtext input/outputが存在しても、repository-local assetにはtokenizerがなく、日本語・未知語品質も未評価である。任意tokenizer download、英訳、text embeddingを暗黙に有効化しない。新しいmodelまたはtokenizerを導入する場合は、通常file、byte数、SHA-256、license、local-only実行、IPC上限、Windows/WSL lifecycleを別Planで固定する。

追加のnear 13枚・far 18枚は、相対path・label・source SHA-256をtest内manifestへ固定し、通常file、link数、PNG、単一frame、source・pixel digestの一意性、pHash距離5以内の重複不在を明示opt-in時に再検証する。画像byte、source URL、商品識別子をlog・文書へ複製せず、権利・再配布条件が未確認のlocal未追跡fixtureとして扱う。全体保持profileの自己参照なしpairwise AUC 0.759259259は事前基準へ未達である。接続方式だけが異なる4枚を画像上の正例へ移した視覚的特徴限定の固定score評価はAUC 0.928571429だが、未達baselineを置換せず、複数queryまたは商品順位の品質を証明しないため、画像rankingを有効化しない。

case2のnear 4枚・far 7枚も画像byteを文書へ複製せず、相対pathとSHA-256だけをtestへ固定する。全体保持profileでAUC 0.642857143・期待順位一致27/53へ改善しても、候補と独立した4方向参照がないため、自己参照を除くcluster診断をproduction scoreまたは本受入評価と表現しない。元Excelは外部link・macroを持たないが非空の作成者metadataを持つため、test fixture、review packet、artifact、commit、配布へ含めず、転記した非個人データだけを使う。

case3のnear 8枚・far 12枚も同じ境界で扱う。相対path、提出label、期待順位、rating、review count、SHA-256だけを固定し、元Excelをruntimeで読まず、作成者・更新者metadataの値をtest、文書、artifact、commit、配布へ含めない。全体保持profileの自己参照除外cluster診断はAUC 0.468750000・期待順位一致80/173であり、独立4方向参照がない限定観測である。画像から「小型（卓上）」や厳密な収納口数を推定せず、画像componentを有効化しない。

`ranking.py` はprovider client、network、LLM、画像encoderをimportせず、strict intent・query plan・normalized product batch・固定ranking profileのdigest連鎖が一致する場合だけ採点する。属性scoreは `ObservedProductAttributes` のbrand、categories、color、material、featuresだけを根拠にし、titleやdescriptionから属性を推測しない。negative matchは観測文字列へのtoken一致を減点内訳として残すだけで、外部商品文を命令、prompt、URL、codeとして実行しない。未観測componentは0点と区別してweightから除外し、image componentは必ずdisabledにする。ranked batchは内部modelであり、provider request ID、digest、raw/effective score、採用言語を通常画面へ直接返さない。

### 13.1 型付き条件と証拠裁定の追加境界（最小domainを一部実装）

[BACKEND.mdの型付き条件設計](BACKEND.md#14-型付き条件と証拠別ランキング最小domainを一部実装) の最小domainでは、trusted registryを実行境界として扱う。

- Bonsaiはattribute key、operator、JSON-nativeな期待値、重要度の候補を既存1回のstrict intent応答で返せるが、condition ID、evaluator ID、Python module、model path、URL、command、weight、証拠優先順位、registry digestを指定できない
- 未知key、型・演算子・単位の不一致を自由文字列や動的importで救済せず、blocking ambiguityまたは固定validation errorにする
- 商品title、description、構造化field、画像、生成画像は全て非信頼入力とし、registry lookup以外のcode dispatch、prompt指示、tool呼出しへ使わない
- exact title parserはregistryに固定した語彙・数値・単位だけを有界に処理する。語句がないことを反対値の証拠にしない
- 専用画像evaluatorは固定asset・runtime・前処理・閾値・digestを持ち、対象attributeへ明示的に許可されるまで使わない。任意model downloadやrequestごとのpath指定を許可しない
- 生成した参考画像・偽画像とCLIP scoreは外観補助であり、実商品の個数、寸法、材質、接続方式、互換性を証明しない。構造化証拠を上書きせず、商品候補や候補画像をCloudflareへ再送しない
- 証拠がない状態を一致へ変換せず、矛盾は `conflict` として固定する。低優先度の画像scoreで上位の構造化値を変更しない
- reference set、candidate pixel、registry、evaluator、ranking profileのdigestを同じ評価へ結び、別versionのscoreやdecisionを混在させない
- 候補集合内のcenter・z-scoreで同じ商品の点数を変えない。候補操作によるranking変動を避け、固定背景集合を導入する場合も内容・権利・digest・更新規則を別途審査する
- browserと履歴へはattribute key、evaluator名、digest、raw score、内部証拠値を直接返さず、「一致」「確認できない」「合わない」のallowlist済み表示理由へ変換する

`typed_requirements.py` と `requirement_evaluation.py` は、strict schema、共通6 keyのregistry v3と検索専用定義、registry digest、改ざん拒否、`unknown`・`conflict`、候補集合へ依存しない順位keyをoffline testで固定した。条件draftはevaluator、module、weight、priority、registry digestを受け取らず、証拠のsource metadataもregistryと一致しなければ拒否する。初期registryは `structured` と `title_exact` だけをexact属性へ許可し、`visual_feature` とCLIP類似度を条件証拠へ使わない。

`product_evidence.py` は、再検証した `NormalizedProductCandidate` と固定profileだけから証拠を作る。専用color field、feature item全体の固定語彙・固定数値形式、商品名のbounded exact語彙・属性label付き数値だけを読み、description、画像、任意正規表現、callback、provider client、LLM、networkを使わない。product、requirement set、registry、profile、source別入力artifactをSHA-256で結び、本文を結果・repr・固定errorへ複製しない。値がない、語句がない、parserがない、専用fieldが未登録値である場合をそれぞれ固定unknown reasonへ変換し、反対値を捏造しない。同sourceの異なる値は最大8件まで保持して `conflict` にし、structuredをtitleより優先する。

`typed_intent_adapter.py` は、再検証した `NormalizedSearchIntent`、repository内registry、固定profileだけから条件proposalを作る。候補順のcondition IDはローカルで付与し、既存の `normalize_typed_requirements()` 以外でtrusted requirementを作らない。未知key、型・演算子・単位・値の不一致、semanticのhard指定、正規化後の重複、上流blocking ambiguityは、候補本文やambiguity messageを含まない固定codeへ変換する。validなpartial requirementは保持しても、issueが1件でもあれば `ready` にしない。intent、candidate set、registry、requirement set、profileを別々のSHA-256で結び、provider client、LLM、network、画像、callback、動的importを持たない。

`typed_ranking.py` は固定registryと固定product evidence profileだけを使い、supplied proposalをintentから再構築したproposalへ完全照合する。blockingまたは改ざん済みproposalは、v3 source rankingと商品証拠の生成前に同じ固定errorで停止する。ready時も商品ごとに証拠と全条件decisionを再生成可能な形で結び、required・preferredの `match` とexcludedの `mismatch` だけを固定分母scoreへ加える。商品dataやBonsai候補はevaluator、weight、module、URL、commandを選択できない。v4 resultは商品本文、URL、候補本文、生artifactをreprへ出さず、schema・profile・batch hash domainをv3から分ける。

これは外部通信を持たないoffline境界である。第1確認、承認、state、ranking-v4後半pipeline、typed表示履歴まで接続済みだが、Bonsai候補の実model意味品質、未対応attributeの専用parser、専用画像evaluator、legacy現行検索、API・UI接続は未実装であり、画像ranking有効化を意味しない。後続adapterでも、商品dataをregistry引数として渡したり、evaluator IDを動的importへ使ったりしない。

- 商品検索の属性抽出は現行Bonsai `POST /chat/completions` を正本とし、OpenAI APIへ自動fallbackしない
- `BONSAI_BASE_URL` の既定loopbackを維持する。remote Bonsaiへ変更する場合は利用者入力がhost外へ出る変更として、HTTPS、認証、送信先、ログ、保持方針を別途審査する
- Bonsaiの応答形式をprovider保証とみなさず、chat response、非空content、content全体の単一JSON object、unknown field、欠落field、strict型を順に検証し、不一致をfail closedにする。Markdown fence、前後の説明文、JSON断片抽出では救済しない
- CloudflareとOutscraperのcredentialを別secretとして保持し、browser、生成prompt、cache、logへ含めない。商品検索用のOpenAI credentialは要求しない
- 商品title、description、外部エラーをuntrusted dataとして扱い、Bonsai、OpenAIその他のLLM、命令実行、tool呼出しへ接続しない
- Cloudflare画像生成は既定OFFとし、第1確認とcall/cost reservation後に先行1枚だけを生成する。条件別偽画像を生成するには、その先行画像への明示了承と新しいexact call予約を必要とする。offline request builderまたはmock HTTP成功だけでは、実Cloudflareの承認済み送信・課金・生成成功と扱わない
- Cloudflare途中失敗後は自動retry、部分画像採用、失敗reservationの解放・再利用を行わない。残数内で先行1枚を作り直して再確認するか、画像なし続行を明示選択し、いずれでも失敗利用量を監査対象へ残す
- Outscraperはexact requestを示す第2確認、15分期限、single-use plan digestが揃うまで呼ばない
- 画像URLはserver-side proxyでHTTPS allowlist、redirect拒否、DNS/IP再検証、8 MiB、4096px、10秒、decompression bomb検査を行う
- Bonsai、Cloudflare、Outscraperの失敗attemptを利用量へ含め、上限超過を人間承認で迂回できないようにする
- 生成画像を実在商品・価格・仕様の証拠として表示せず、常にAI生成と示す
- 将来APIは認証済み主体からownerをserver-sideで決定する。実装済みrepositoryは全操作でownerを必須にし、session IDや公開用locatorだけを認可根拠にしない
- 履歴の表示モデルはallowlistで構築し、郵便番号、お届け先、内部ID、owner、completion key、provider、model、token、digest、raw scoreを返さない
- 履歴削除は対象ownerを再検証し、結果スナップショットと専有生成画像を単一transactionで削除する。失敗はrollbackし、削除再試行から外部APIを呼ばない
- 検索履歴はcache TTLと分離して完了日時から30日で期限切れにし、期限後は一覧・詳細・画像取得へ返さず、明示した期限削除で結果と専有生成画像を物理削除する。定期実行は未実装である
- 通常pytestとCIはBonsai、Cloudflare、Outscraperをmockし、live markerだけでは費用・送信内容の人間承認を代替しない

live試験の要求範囲、費用提示、個別承認、停止条件は [DEVELOPMENT.md](DEVELOPMENT.md#6-live結合試験) を正とする。


### 参考画像失敗の診断境界

EXEC-081の `CloudflareFailureDiagnostic` はclosed stageと、HTTP失敗時だけの100〜599の整数status（200を除く）をstrict・frozen・extra-forbidで受ける。`ReferenceReview` とbackend E2Eの安全な出力へ伝えるが、response body、header、URL、例外文字列、token、画像、検索入力を診断に含めない。HTTP 429のidentity encoding・JSON応答だけは最大8 KiBをメモリ内で検査し、単一errorの既知整数code 3036 / 3040を `provider_error_code` に保持する。上限判定時の追加読込は最大1 KiB。重複key、不正JSON、未知code、複数error、読込失敗はcodeをnullにし、元のHTTP statusを維持する。その他のHTTP非200ではbodyを読まず、全経路でresponseとsessionをcloseする。診断追加は再送信の承認ではなく、失敗後に自動retryしない。

EXEC-082の材質判定は専用fieldと有界titleだけを根拠にし、CLIPを材質証拠へ昇格しない。registry v2・evidence parser v2のdigestを承認とrankingへ結ぶ。材質termの補完もsource-groundingと元の強さを維持し、欠落・曖昧・件数超過を成功扱いしない。


## 検索専用属性の提案境界

EXEC-083ではBonsaiが不足属性のlabel・meaning・source_quoteと型付き条件を提案する。EXEC-084で固定登録を共通6属性へ限定し、カテゴリ固有属性名は原文の値や機能から推論できるようにした。原文に属性名がないことだけでは拒否しないが、値や条件関係の根拠検証は維持する。原文はBonsaiへ保持して渡し、SudachiPyの位置情報とbackendの比較規則で根拠を照合する。意味を形態素解析だけで保証せず、第一確認に提案を残す。根拠なし、上下限逆転、単位不整合、否定・希望の切落し、対応不能なORは確認待ちとする。

検索専用属性の識別子・weight・evaluator・priorityはbackendが生成し、modelの実行code・任意evaluator・共有registry更新を受け付けない。定義全体をregistry・proposal・承認digestへ束縛し、別検索への混入と変更後の旧承認利用を拒否する。商品証拠v4は正規化済みfeatureの明示labelと値だけを追加属性へ対応付け、欠落を推測で埋めない。追加のprovider呼出しは発生しない。新規の実Bonsaiによる定義品質は別の明示承認付き検証を必要とする。


## Bonsai単体診断の応答ログ

利用者の「テストにおける応答を全てログに保存する」指示により、EXEC-087の固定合成入力を使う単体診断だけはraw応答をprivate fileへ保存する。テスト専用transportは127.0.0.1のHTTP・既存の固定header・1 call・retry0を要求し、repository内や既存pathへの保存を拒否する。新規directory0700・file0600へ成功・HTTPエラー・不正JSONの生成応答本文を保持する。response1 MiB上限と900秒のserver停止境界は維持し、上限超過・中断は受信済みprefixと不完全状態を残す。request header・認証情報・生例外を出力せず、raw本文と正規化条件はstdout・文書・artifact・commitへ転載しない。実利用者入力、Cloudflare、Outscraper、本番loggingの契約をこの例外で拡張しない。


EXEC-093では原文の明示事実を入力別生成schemaへ束縛する。生成schemaだけでは外部応答の正しさを保証できないため、完全schema検証後も未加工応答を原文の事実契約へ照合し、条件欠落・値の変更・定義改変を固定エラーで拒否する。利用量は失敗として閉じ、自動retryしない。source由来の定数はJSONとしてescapeし、命令やcodeとして実行しない。正解データやテスト判定器をproduction生成へ渡さない。新しいraw入力保存やcredential利用は導入せず、全応答保存は利用者が授権したprivate単体診断だけに限定する。

省略名の生成結果は仕様名のみであり、実行可能な分類器や比較規則は生成させない。wireのattribute_names_jaと原文事実から作る定義文はbackend由来であり、モデルが意味説明を正しく生成した証拠として扱わない。文法の文字列境界と未解析句の確認待ちも回帰対象とする。

仕様名推論のuser messageはsource_inputとunnamed_quantitiesを持つ非信頼JSONであり、元の自然文をsystem messageへ展開しない。モデル応答が指定以外のfield・名前数・数値比較文を含む場合は拒否する。仕様名を原文の数値条件へ結合する前後で、元の応答provenanceを維持する。

EXEC-094では日本語文字を含まない推論名と、既知boolean属性名の数値属性への流用を拒否し、失敗予約・retry0を確認した。文字種検証だけで日本語の正しさや意味的整合を保証しない。固定合成入力の承認済み試験ログは/tmpのみへ依存せず、repository外の永続private directoryへ保存する。移した応答はhashと0700/0600の権限を確認し、元の記録を上書きしない。

生成時の名称patternも日本語文字を要求し、全分岐で100文字上限とJSONの引用符・escape・制御文字の除外を維持する。単位名の大小文字変形は単一文字のUnicode変形も除外する。受信時の正規化・再検証は引き続き必要であり、この文法が名称の意味を保証するとは扱わない。

### 数値属性の未確定候補と実行の分離

EXEC-096の数値属性候補はモデルの提案として扱い、数量だけの引用から推論した名前は承認可能なrequirementへ昇格させない。原文の名前と数量の対応を別途要求し、adapterのblockingフラグだけに依存せず、registry・typed proposal・query plannerで再検査する。既存registryの注入やambiguitiesの除去でも未確認候補は実行できない。属性を明記した入力の再処理を必要とし、単なる了承は根拠を追加しない。

RAG用の定義選択境界でもモデルのIDを提案IDに限定し、一意な明示対応がなければ実行IDはNone。confidence、正解ラベル、model-authored proofなどの追加fieldは受け付けない。不正JSON、候補外ID、重複ID、打ち切りはinvalidで停止する。検索文や全応答の永続記録は今回の承認済み合成診断に限りrepository外0700/0600へ保存し、実利用者の生データを通常ログへ記録する変更は行わない。


### Candidate画像付きflowの承認境界（EXEC-101）

CandidateSearchFlowがcandidateサービスと画像状態を所有し、planのowner/session・15分期限・digestを各段階で検査する。参考1枚の了承後だけN枚の偽画像を生成し、その後の永続single-use承認を消費してから商品取得を許す。flow固有nonce・attempt・policyを画像bindingへ含め、現在flowの再生成時に古い確認を使用できなくする。初回を含め最大3生成attemptで、利用量の失敗記録を消さない。実行中の再入・二重承認はstateの確保で拒否する。

CandidateRankingのJSON復元は承認・実行状態の復元にならない。画像付きresultは所有flowだけから完成し、共通IntentReviewやTypedRankedProductBatchの制約を緩めない。履歴保存の再試行には同じownerと保持中のpayloadを使い、providerを再呼出ししない。profileごとの品質metadataを検証し、旧経路の実測精度を新経路へ転用しない。今回の検証はmock provider・固定embedding・一時SQLiteに限定し、外部送信やlive実行の許可を追加していない。

### Candidate実テストの診断ログ

Candidateの準備失敗はschema_versionと許可された固定codeだけを出力する。`candidate_failure_diagnostic()` は型付き例外のdiagnosticも再検証し、任意文字列・未知code・余分なfieldを含むものはunexpectedへ置換する。応答本文、入力の節、不正なモデル出力値、生例外、認証情報を診断へ複写しない。既存のHTTP応答status/byte数/hashログと合わせて停止境界を識別する。本文が保存されていない過去実行の拒否理由をこの変更から遡って推定しない。


OPUS-MTの任意接続は、管理者が指定したローカルPython/資材だけを使う。モデル/語彙/tokenizerとworkerのhashを確認し、1回最大2句・各100文字をstdin JSONで渡す。入力をargvへ含めず、環境変数はOS用の最小項目だけを継承する。翻訳processは30秒で停止し、stderrを破棄し、応答の件数/型/サイズを検証する。モデル取得と外部翻訳APIへのfallbackはない。既存の辞書hitや辞書エラーで翻訳を実行しない。訳語は未確認の検索候補であり、仕様充足/ランキング根拠にしない。


MobileSAMによる任意の領域抽出も別processへ隔離する。準備済みのsource/checkpointを固定manifestで照合し、推論中にpackage/modelを取得しない。認証用環境変数を渡さず、local_files_onlyとoffline設定を使用する。最大36画像×3対象・512px、600秒、候補数・mask応答byte数・診断JSONを検証する。このprocess分離とoffline設定はOSによるnetwork sandboxではない。資材の差替えを禁止した検証環境で運用し、iGPU対応や本番の資源適合は別途確認する。


EXEC-116のSigLIP 2 workerは固定ローカルPythonを-Iで起動し、credential環境変数/標準入力を継承しない。ネット接続を遮断し、local_files_only、trust_remote_code=false、safetensors固定でモデルを読み込む。資材SHA256を実行前後で検査し、36画像/600秒/応答128000bytesの上限を設ける。画像は224pxへ縮小してprivate一時directoryで受け渡し、終了時に削除する。worker標準出力/エラーを利用者へ転送せず固定エラーにする。runtime/profileが異なる旧CLIPの埋込みや採点を再利用せず、モデル自動fallbackはしない。
