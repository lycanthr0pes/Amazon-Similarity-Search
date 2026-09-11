# 残作業と利用者側で用意するもの

## 次期フロントエンドを自前開発する（2026-09-11）

外部納品待ちを解除し、このリポジトリで次期画面を作成する。今回は関連文書の更新までとし、次は [画面設計](docs/FRONTEND.md#11-次期フロントエンドの自前開発方針) に基づく画面構成・状態・API契約と実装方式の整理へ進む。その後、合成データによる画面実装・操作確認、ローカルAPI接続の順に進める。実サービス検証は既存の事前説明と明示承認を必要とする。技術スタックはReact + StyleXに決定した。Figmaはレイアウトの参考、色・文字・装飾・操作配置は [視覚仕様](docs/FRONTEND.md#13-次期uiの視覚統一契約) を正本とする。全ボタン共通の幅・高さ、配置先、ビルド・起動手順は後続設計で決める。今回の変更を画面や接続の完成とは扱わない。

先行する [オフラインモック](docs/FRONTEND.md#14-オフラインモック実装予定) は任意の自然言語を受け、確認画面に入力を保持し、固定の合成条件・商品・画像で結果表示まで操作できるものとする。画像なし経路・戻る・二重操作防止・指定アニメーションを含め、フォントと画像はローカル資材で用意する。実バックエンド・Bonsai・外部API・credentialは不要とし、実サービスへ自動接続しない。UIとモックの実装・起動・ブラウザ確認は未実施。

対象部位の提案と形状専用比較をcandidate/履歴へ接続した（EXEC-104）。ローカルCLIPSegは実写真で内部の欠け・複数商品の混同が残り、自動切出し/実順位品質は未達。iGPU性能も未測定。既知maskのoffline成功と実商品品質を分け、対象領域の品質を改善・検証する。詳細は [EXEC-104](docs/GOAL.md#exec-104-属性別の画像比較と対象領域の分離)。以下は以前の経過。

比較可能なscoreの保持を実装した。原語英訳をタイトル比較へ接続し、candidateの画像順位は候補分布の校正条件から切り離した。前回と同一24商品・保存CLIP数値の再評価で画像available0→24、総合0が23→0。全体offline2957件成功。新規検索/画像取得/モデル推論はなく、完了済み結果GET1回後の再計算なので、新規実E2Eや未知順位品質の合格とは別である。新candidate-lexical-clip-v3を今後の実検索で確認することが残る。詳細は [WORKLOG177](docs/WORKLOG.md#177-総合0の原因を修正し相対順位の保留基準を縮小2026-09-10)。以下は修正前の診断記録である。

全24件の画像unknownの原因を特定した。CLIP比較は全件scoredだが、正規化marginが+0.3264〜+0.8605に収まり、ゼロ交差も±1飽和もないため校正がinsufficient_diversityで保留し、全件の画像スコアを破棄していた。画像取得/推論の失敗ではない。検索候補の分布に依存する校正と、類似度による順位利用の設計を見直す必要がある。今回は診断のみで製品規則は未変更。詳細は [WORKLOG176](docs/WORKLOG.md#176-実画像評価unknownの原因を校正規則に特定2026-09-10)。

2026-09-10、承認済み画像2枚を再利用した実検索が完了。Outscraper1 task/12 pollsで24商品と画像24枚を取得し、CLIP7 batches・ランキング・履歴再読込まで391.621秒で到達した。全体offline2940件成功。ただし画像評価は全24件unknown、英語の商品名が多く単語一致を含む総合scoreは23件0のため、順位品質は未達。画像評価の保留理由の診断と、日本語検索語に対する英語商品名の採点が残る。詳細は [WORKLOG175](docs/WORKLOG.md#175-保存画像から実検索を再実行しランキング履歴へ到達2026-09-10)。以下の候補取得中停止は前回実行の記録である。

OPUS-MTを未収録商品句の英訳へ接続した。実CLIに独立Python/モデル資材を指定すると、Bonsai日本語名→原語/提案名各1英訳→候補確認へ進む。辞書hitでは辞書訳を維持する。接続後の全体offline2928件と実ローカル翻訳3句の接続が成功。承認済みbackend実E2Eは画像2枚生成と実検索1 task/8 pollsまで進み、候補取得中に停止。確認待ち込み15分上限と停止時刻が一致し、ランキング/表示履歴は未検証。以下の「OPUS-MT未接続」はこの接続より前の記録である。

2026-09-10、利用者が辞書未収録10商品句のOPUS-MT精度5/10（50%）を合格として受け入れた。過去の観測値は保持し、精度改善待ちを解除して画像生成を含むbackend実E2Eを準備する。OPUS-MTは単体評価環境のみで、現行入口には未接続。今回は既存の辞書/文脈解析・Bonsai経路を検証する。実行範囲と承認条件は [EXEC-103追加判断](docs/GOAL.md#exec-103追加判断と実e2e準備2026-09-10)。

以下のOPUS-MT採用保留という記録は今回の利用者判断より前の評価履歴であり、現在の受入判断を上書きしない。製品への接続は別途未実施である。

OPUS-MT日英モデルのローカル比較を完了。「ヘッドフォン」表記で試し、デスク下のハンガーは正しく訳せたが、12商品句の概念充足は通常精度/INT8とも6/12。INT8は中央値0.046秒・peak RSS153.9 MiBだった。英訳の対象欠落が残るため、製品への採用は保留する。詳細は [WORKLOG168](docs/WORKLOG.md#168-ヘッドフォン表記でopus-mt日英翻訳を比較2026-09-10)。

辞書候補0件では、辞書を使わないBonsai直接推論を実装済み。追加文脈のない商品名も対象とし、生成後に辞書へ再照会しない。実Bonsai6件で新経路を確認したが、英訳の概念充足は3/6で改善余地が残る。候補確認・原文条件の検査を維持する。詳細は [WORKLOG167](docs/WORKLOG.md#167-辞書候補0件をbonsaiだけの名称推論へ分岐2026-09-10)。

2026-09-10の未知名検証は品質未達。文脈からの補完0/4、未収録名明記時の英訳0/4で、辞書語義の誤選択2件も確認した。語義選択と具体的な商品名/英訳作成の分離が残る課題。詳細は [WORKLOG166](docs/WORKLOG.md#166-未収録の商品名補完英訳を実bonsaiで検証2026-09-10)。

最新（2026-09-10、[EXEC-103](docs/GOAL.md#exec-103-辞書と文脈による検索語の自動選択)）: 商品名候補を条件query検証より先に作るprepare経路へ変更した。原文の対象・修飾句を保持し、複合語辞書検索と必要時のBonsaiによる商品名提案を行う。未収録提案と辞書選択は区別し、候補選択後も原文条件を捨てない。準備が停止してもproduct_reviewから候補を確認できる。

依頼表現の活用を文脈と誤認する問題と、正規化された略語の係り受け誤判定による複合語分断を修正した。商品候補が1件でも、意味を限定する文脈があれば適合を比較する。未知入力全般の精度は未達として独立評価を継続する。用途・仕様が現行規則で解釈できない場合は、商品名候補だけ解決しても検索/画像生成を停止する。この条件解釈の通過性は残課題で、名前の補完を商品の仕様充足と扱わない。

以下はこれまでの到達点と検証履歴。旧Bonsai商品採点・語句生成の記録は現行仕様を上書きしない。


[EXEC-101](docs/GOAL.md#exec-101-candidate経路の画像承認clip履歴接続) で、新candidate専用の `CandidateSearchFlow` を追加した。Sudachi検索語・Bonsai視覚提案→参考1枚→了承→条件別偽画像→最終画像承認→候補取得→属性選択→数値/Bonsai/CLIP評価→SQLite履歴の詳細・一覧・画像再読込をofflineで接続した。従来の `prepare_candidate_search` は低水準の候補取得/数値評価部品として保持し、画像付きの入口には新flowを使う。

新rankingは `candidate-semantic-clip-v1`。必須条件の充足を優先し、Bonsai意味80%・CLIP20%、画像不明時は意味点数のみを使う。実品質は未測定として履歴の精度値はnull。数値名が未記載の条件は取得後の具体的属性選択まで保留する。結果JSONのDecimal復元は[EXEC-100](docs/GOAL.md#exec-100-candidate結果jsonのdecimal復元)で修正済み。

次は実Bonsai・画像生成・実CLIP・候補取得の品質/費用/実行条件を固定して検証する。新flowは視覚条件1〜3件を持つ単一processの注入backendで、既存live入口・API・次期frontendは未切替。視覚条件なしや画像省略での新履歴接続、process再起動後の途中状態復旧は対象外。旧経路の合格率を新経路へ流用しない。次期フロントエンドは自前開発へ移行し、今回の文書更新後に設計・実装・接続を進める。

過去の実検索E2E再試行では、参考画像の生成段階で停止した。Bonsai 1 call・Cloudflare 1 call、Outscraper未実行。追加送信・再試行は行っていない。[EXEC-081](docs/GOAL.md#exec-081-参考画像生成失敗の安全な診断) の承認済み限定再実行ではCloudflareのHTTP 429を確認した。追加調査ではAnalytics利用量照会が権限不足だった。当日の9B生成9枚と公式単価から日次無料枠超過が有力だが、実計上量・契約plan・内部codeは未確認。既知429 codeの安全な診断を追加し、画像生成は追加していない。詳細は [WORKLOG 111](docs/WORKLOG.md#111-4方向を除いた実検索backend-e2eを再開2026-09-08) を参照する。4方向生成を除いた現行仕様は [EXEC-080](docs/GOAL.md#exec-080-4方向生成を製品フローから除去) を正とする。

最新の単発確認では、2026-09-08 17:38 JSTに現行4BモデルがHTTP 200を返し、13.341秒・1 call・retry 0で参考PNGを生成できた。現在の疎通は成功したが、過去429の内訳と検索E2E全体は未確認。詳細は [WORKLOG 114](docs/WORKLOG.md#114-現行4bモデルの画像生成疎通を再確認2026-09-08) を参照する。

最新の実検索E2E再試行は完走した。Bonsai 1 call→参考画像1枚→人間了承→偽画像1枚→画像/query最終了承→Outscraper 1 task・6 polls→商品画像24枚→CLIP 7 batches→24商品ranking→履歴再読込まで1 passed・retry 0。履歴の画像2枚と商品表示24件も一致した（[WORKLOG 115](docs/WORKLOG.md#115-4方向を除いた実検索backend-e2eの再試行2026-09-08)）。

[EXEC-083](docs/GOAL.md#exec-083-入力に基づく検索専用属性の追加) と [EXEC-084](docs/GOAL.md#exec-084-共通属性だけをプリセットにする) により、共通6属性以外の仕様を検索ごとにBonsaiが提案する構成とした。実単体で判明した生成順序・比較方法・条件の混同を [EXEC-088](docs/GOAL.md#exec-088-独自属性の生成順序を修正) と [EXEC-089](docs/GOAL.md#exec-089-独自属性の比較方法と条件の強さを修正) で修正した。EXEC-089時点の実Bonsai単体は白色・容量350ml以上・食洗機対応を全てrequiredとして抽出し、3条件・検索専用2属性・readyを含む固定9項目に合格。失敗・成功両方の応答全文をprivate logへ保存した。固定入力1件の合格であり、未知カテゴリの推論品質と新しい実検索の順位監査は未検証。次期frontendは引き続き未接続。

[EXEC-090](docs/GOAL.md#exec-090-別カテゴリ5入力の実bonsai単体検証) で別カテゴリ5件を同じmodel・promptへ各1回送った。初回自動基準は0/5、保存応答の内容確認ではヘッドホン1件が成功（意味判定regexの同義語不足）。テーブルは木材欠落と「丸い」の原文照合失敗、リュックは単位誤りと撥水→防水への置換、モニターはインチ／inch表記の照合失敗、キーボードは対応可否の数値化と除外の真偽反転が残る。その後 [EXEC-091](docs/GOAL.md#exec-091-5入力の失敗箇所を修正し再試験) でモデル指示・生成順序、共通形状・同値単位の照合、評価語彙を修正した。修正途中は2/5、最終設定では同じ5例が全て合格し、各1 call・retry0で全条件とreadyを保持した。既存マグカップ1件も同じ最終設定で既存9項目に合格した。最初の誤りは上記の履歴として残し、修正した既知例への合格を未知カテゴリや実商品rankingの品質へ一般化しない。

[EXEC-092](docs/GOAL.md#exec-092-未使用4カテゴリの属性推論精度を測定) で、最終設定を変えず未使用のテント・ミシン・プリンター・顕微鏡を各2入力、計8回測定した。完全合格は2/8（25%）、事前の意味定義判定を含む条件合格は11/19（57.9%）で、未知カテゴリの品質基準は未達。希望と除外の取り違え、倍率を幅へ置換、重量2kgを2000kgへ誤る例を確認した。意味説明不足も別に記録し、全応答を保存した。新しい実商品rankingの評価は未実施。この8例も今後は使用済みデータとして扱う。

[EXEC-093](docs/GOAL.md#exec-093-原文の事実と属性推論を分離する) で、原文から確定した数値・単位・比較・希望/除外をbackendが保持し、Bonsaiは省略仕様名だけを推論する構造にした。カテゴリ別の正解辞書は追加していない。最終backendへ保存実応答をoffline再投入した既知12例は8/12（元の8例は7/8）、最終設定で初回実測した新規2例は1/2だった。offline 2300件は成功したが、未知仕様名の意味品質は合格水準に届いていない。全43生成応答をprivate logへ保存し、誤った属性名を品質合格に読み替えていない。詳しくは [WORKLOG 130](docs/WORKLOG.md#130-原文の事実と仕様名推論を分離し未知品質の未達を確認2026-09-09) を参照する。

順位監査で見つかった材質未判定と材料名の色誤抽出は [EXEC-082](docs/GOAL.md#exec-082-材質条件と材料名の色誤抽出を修正) で修正した。修正後の確認は合成回帰であり、保存済み24商品の順位と旧履歴は変更していない。新しい実検索での順位品質は未確認。

最終更新: 2026-09-11

## 結論

- 旧6-call E2Eは23商品ランキングと履歴再読込まで限定live成功したが、4方向品質は診断を重ねても不合格だった。利用者判断で4方向生成を除去したため、追加視点診断・3D生成・視点変換API調査は終了する。過去の品質不合格は [ISS-002](docs/ISSUES.md#iss-002-4方向指定の生成画像がほぼ同じ向きになる) に残す。

- 新フローは参考画像1枚で確認待ちになり、了承後に条件別偽画像N枚（1〜3）だけを生成する。通常2〜4 calls、作り直し1回を含む最大8 calls。Figma・目標仕様も同期する。生成物確認→商品検索最終承認→既存暫定ranking・履歴の順序を維持し、新フローの固定合成1条件では実サービスを使うbackend E2Eが完走した。未知条件の品質、API・UI・本番配置は未確認。
- 次期検索の既存オフライン経路は、型付き条件を使う `typed-ranking-v4` へ移行済みである。これとは別に、利用者判断でaccuracy 0.875のcounterfactual v4を暫定採用するproduction backend部品を追加した。新しい `typed-ranking-v5-counterfactual-provisional` だけが画像weight 0.10を有効にし、必須条件の確認状態を総合点より先に扱う。旧 `ranking-v3`、`typed-ranking-v4` と低位の4方向Cloudflare adapterは互換維持し、上位の画像生成入口は先行1枚の了承後に後続生成する順序へ更新した。
- Bonsai request v5では、非空の生成用schemaにより旧 `content_not_json` を解消し、非blocking intentを後段へ渡す前に検索queryを作れることも必須にした。EXEC-055の承認済み先頭1件・合計1 callは、現行orchestratorでstrict intentとtyped proposalを処理し、query plan・query digestなしの `BlockingIntentReview` へ到達した。2件目、再試行、dataset assessment、商品取得、ranking、後続providerは実行していない。本文を保存していないためblocking理由と妥当性は断定しない。typed ranking品質はまだ測定できていない。
- EXEC-057でrequest v6へ更新し、固定promptだけをsystem messageへ置き、生成用schemaを `response_format.schema` へ1回だけ送るようにした。完全schemaはmodelへ重ねず、別digestとapplication側のstrict最終検証に維持する。本番起動例はprompt cache、context 8,192、parallel 1を明示した。固定prompt 883 tokensと有効な最大入力4,000 tokensだけで4,096を超えるためcontext縮小は採用していない。Core i5-13600KF・WSL2・CPU版の出力1 token benchmarkでは、変更前相当cache無効の中央値142.56秒からcache warm中央値1.236秒へ約115倍・99.1%短縮した。full JSON生成、実検索、Core Ultra性能は未確認で、Vulkan buildも未実施である。
- EXEC-058で、request v6と2回目のprompt cache hitを同じlocalhost `llama-server` で確認する明示opt-in結合testを追加した。明示承認後のCore i5-13600KF・CPU版実行では2 callsともfull JSON・strict intentを通過し、2件目はprompt 925 tokens中891 tokens、約96.3%をcacheから再利用した。1件目99.729秒、2件目579.494秒だが、入力とcompletionが異なるためwall時間差をcacheによる速度差とは扱わない。Core Ultra性能は未確認である。
- EXEC-059で、上記の時間差を推測せず調べるため、同じ固定合成request v6を2回だけ送ってprompt処理とcompletion生成を分離した。両方487 completion tokensでfull JSON・strict intentに成功し、2件目は923 / 924 prompt tokensをcacheした。prompt時間は43.655秒から0.124秒へ353.47倍・99.72%短縮、wall時間は137.311秒から90.440秒へ1.52倍・34.13%短縮した。warm wallの99.82%は生成時間であり、次の速度改善対象はcompletion生成である。Core Ultra性能は未確認である。
- EXEC-060でrequest v7のcompact wireへ更新した。値がないscalar、空list、価格なし、固定JPYと非該当価格fieldを省略し、受信後は従来の完全19-field draftへ決定的に復元してstrict検証する。代表fixtureはlocal Bonsai tokenizerで126 tokensとなり、同じ意味のminified完全形式181 tokensより30.4%少なく、196-token目標を満たした。`max_tokens=196` は設定していない。承認済みlocalhost診断では365.12秒で応答未完了のため手動停止し、server内の生成継続までは確認したが、completion token数、strict結果、速度改善率、意味品質は得られなかった。Core Ultra性能は未確認である。
- EXEC-061で現行requestをv8へ更新し、検索可能compact wireを最大12種類の固定field、確認待ちを `ambiguities` 1 fieldへ分離した。商品名・brand・modelは48文字、termは32文字、各term list・typed condition・set値は4件、ambiguityは2件・各96文字までである。承認済み2-call診断はstrict intentとwarm wall 17.625秒を確認した。追加の承認済み1-call development regressionは50.628秒・82 completion tokensだったが、明示条件欠落と不正typed conditionでblockingとなった。語彙非依存の原子的条件分解、未知語の原文保持、value-type別schemaへoffline修正し、同一入力のbodyを15,032 bytesから14,859 bytesへ減らした。修正後の承認済み1 callは53.595秒・248 completion tokensでstrict intentへ到達したが、価格・除外条件欠落と入力にないtyped conditionによりblockingで停止した。Outscraperは未実行である。追加モデルcallなしで、入力根拠のあるtyped条件だけを保持し、明示JPY上下限と未知語を含む除外対象をローカル復元するadapterを実装した。日本語の根拠照合と否定範囲はSudachiPy `SplitMode.C` の形態素・品詞・NFKC/casefold済みsource offsetへ統一し、未知複合語内の部分一致と二重否定を拒否する。取得済み応答相当fixtureはreadyとなるが、adapter修正後の再推論は未実施である。
- 上記adapter修正後の承認済み1-call localhost再実行は83.398秒、902 prompt tokens、290 completion tokens、response 1,895 bytesで完了した。未知語2種、5,000〜10,000円、除外対象、二重否定拒否、strict intent、ready proposal、query planの全固定判定が成功した。retry、Outscraper、Cloudflare、credential、外部network、課金はなく、server停止・port非listenも確認した。単一の固定合成入力によるdevelopment regressionであり、未知入力全般や実商品検索の品質は示さない。
- 承認済みの固定合成queryを使う実Outscraper試験を1回実施した。task作成1回・自動retry 0、同一taskのpoll 9回、251.795秒で候補24件を受信し、24件すべてがv2応答契約と観測値だけの正規化契約を通過した。生応答、商品本文、商品URL、ASIN、provider request ID、APIキーは出力・保存していない。これはOutscraper接続と正規化の単一試験であり、Bonsaiからの一続きのE2E、ranking品質、UI、production運用、実請求額は未確認である。
- 一続きE2EのBonsai段階では、source grounding、商品名field過剰制約、SudachiPy連続接頭辞欠落を順に修正した。接頭辞修正後の承認済み最終確認は、1 call・retry 0、60.366秒、906 prompt tokens、268 completion tokensで `ready` となり、query `超低背 ワイヤレス キーボード`、価格5,000〜10,000円、必須語3件、除外語1件を保持した。別の明示承認後、このqueryによるOutscraper taskを1回だけ作成し、自動retry 0、同一taskのpoll 8回、221.458秒で24候補を受信した。24件すべてが次期v2の正規化・typed rankingを通過し、rejectは0件、利用量予約は `succeeded` となった。生応答・商品本文・URL・ASIN・provider ID・credentialは保存せず、一時stateも削除した。個々の条件一致と順位品質、browser・UI・production E2Eは未確認である。
- 暫定本番のcounterfactual参照生成はCloudflareを正本とする。旧経路ではdesired 1枚と条件別counterfactualをexact `1 + N` calls、最大4 calls、自動retryなしで生成するrequest・HTTP・可変利用量予約、永続single-use人間承認、商品先頭画像proxy、固定local CLIP、label-free較正、ranking v5、別schema 5.0履歴までのbackend経路を実装した。gpt-imageは画像評価テストだけに使う。EXEC-080で上位入口を先行1枚の了承後に条件別counterfactualだけを生成する順序へ接続した。旧経路の実通信結果は後続の履歴項目に記載し、新フローの実サービス成功とは扱わない。
- `CLOUDFLARE_ACCOUNT_ID`・`CLOUDFLARE_API_TOKEN`の型付き設定と、固定合成条件の基準画像1枚だけを1 callで作る二重opt-in live runnerを追加した。tokenはmaskし、retry 0、生応答非保存、正規化PNGの0600 exclusive保存をoffline mockで確認した。最初のlive試行前には料金・送信契約を再提示して別承認を得る境界を維持した。
- 初回Cloudflare live試行は1 HTTP attempt・retry 0で12.43秒後に固定エラーとなった。段階diagnostic追加後の別承認1 callは、28.246秒後に `image_content` で停止した。公式契約はBase64画像を保証するだけなので、raw画像をJPEG・PNG・WebPへ限定して完全decodeし、exact 512×512・単一frameを確認後、metadataなしRGB PNGへ正規化するようoffline修正した。修正後の別承認1 callは11.728秒で成功し、175,824 bytes、512×512、単一frame、metadataなしRGB PNGを `/tmp/amazon-explorer-cloudflare-reference.png` へ0600で保存した。3回ともretry 0であり、生応答とcredential値は保存していない。これは固定合成条件の基準画像1枚のlive結合成功であり、4方向set、counterfactual生成、画像品質、実請求額、production E2Eは未確認である。
- 旧counterfactual Cloudflare経路の限定診断として、固定合成入力「白い陶器製マグカップ」と視覚条件「白い」1件だけをdesired＋counterfactualのexact 2 calls・retry 0で実行する専用live runnerをoffline TDDで追加した。focused 9 passed・1 skipped、関連回帰151 passed・2 skipped、標準offline gate 1,875 passed・13 skipped・5 deselectedに成功した。料金・条件を再提示して明示承認を得たlive testも1回だけ実行し、1 passed、2 calls、retry 0、18.388秒でPNG 2枚の正規化保存と「白い」だけを反転した画像内容を確認した。これは固定合成1条件の最小結合成功であり、未知条件全般、CLIP、実商品、ranking、実請求額、production E2Eは未確認である。
- Outscraperの完了結果を商品正規化とランキングへ一続きで渡し、結果あり、正常0件、工程別の固定失敗を区別する検索後半の処理は、オフライン境界まで実装済みである。
- 次期検索フローは、Bonsaiからreadyまたはquery-less blockingの第1確認、任意画像、第2確認、Outscraper、正規化、ランキング、完了、履歴保存までを、独立したオフラインバックエンド境界として接続している。query-less blockingの第1確認はlocalhostの実応答1件でも結合確認した。新しい画像生成フローでは失敗利用量を残し、残数内で先行1枚から作り直して再確認するか、画像なしで続ける。
- 商品画像の安全な取得部品は、配信元名を1回だけ名前解決してTCP用IPv4・IPv6を最大8件に限定する部品、その名前解決をWindows/WSL互換の `spawn` 子processへ隔離する5秒application deadline、検証済みIPへ1回だけ直接接続し、元の配信元名でTLS証明書を確認して8 MiB以内で通信を閉じる部品、起動時の許可配信元と各部品を一つに固定するproxy serviceまで実装した。process間の結果は最大512 bytesのASCIIだけに限定する。主な確認は合成allowlistと注入したprocess・pipe・clock・DNS・socket・TLS・HTTP fixtureで行い、WSL2では外部DNSを呼ばない固定失敗経路の `spawn` を1回確認した。5秒は `Process.start()` のOS起動時間を絶対に制限する値ではない。運用ドメイン、実サイト、Windows nativeでの動作は確認していない。
- 固定CLIP modelは `models/clip-vit-base-patch32-12b36594/` にONNX形式の3 fileとして配置し、SHA-256を固定した。前処理は縦横比を維持して画像全体を224×224内へ収め、残りを正規化後0となるモデル平均値で埋める。profile IDをruntime digestへ結び、旧center-crop embeddingとの混在を拒否する。ONNX Runtime 1.23.2のCPU provider、最大4枚、30秒application deadline、最大約2.4 MBの親入力と約8 KBの子process戻り値、terminate・killを維持した。画像scoreは色、外観形状、商品種別など画像で確認できる特徴だけの補助評価とし、有線・無線は商品名と構造化された観測属性で判定する。case1のnear 9枚・far 18枚はpairwise AUC 0.759259259で事前基準0.80へ未達である。接続方式だけが異なるf2・f4・f7・f10を画像上の正例へ移した補助評価もAUC 0.928571429で基準以上だが、単一条件に限られるため画像採点は無効のままである。scoreから接続方式、用途その他の構造化属性を補完しない。modelと画像はlocal working treeにあり、Git追跡・配布はしていない。
- case2として「筒状・長い・縦・金属製・収納、追加で四角い・黒い」のnear 4枚・far 7枚、視覚特徴、構造化特徴、期待順位、rating、review countを受領した。候補とは独立した4方向参照がないため正式な画像ranking評価ではなく、near候補だけ自己参照を除くcluster診断とした。全体保持前処理では固定ONNXのAUCが0.642857143、期待順位との順序一致が27/53へ改善したが、画像採点を有効化できる本評価ではない。特徴が同じ候補間のレビュー品質による期待順2組は現行ranking v3と一致した。
- case3として「収納口2つ・小型（卓上）・縦・収納」のnear 8枚・far 12枚、視覚特徴、構造化特徴、期待順位、rating、review countを受領して固定した。独立4方向参照がない自己参照除外cluster診断ではAUC 0.468750000、期待順位一致80/173だった。near平均0.858911962とfar平均0.858491016はほぼ同じで、far中央値0.863038093がnear中央値0.861306486を上回るため、画像だけでは分離できていない。
- case3の結果を受け、自然文を型付き条件へ分け、構造化商品情報・限定した商品名parse・将来の専用画像評価・CLIP外観scoreを条件ごとに裁定する設計を確定した。型付き値、9 keyのtrusted registry、証拠の `match`・`mismatch`・`unknown`・`conflict`、Bonsai候補adapter、商品証拠adapterに加え、必須状態を総合点より先に扱う `typed-ranking-v4` を実装し、第1確認、承認、検索state、検索後半、表示用履歴までオフライン経路で接続した。未知条件を分母から外さず、明示的な必須不一致を価格・画像・レビューで打ち消さない。画像採点は無効のままである。
- 未使用holdoutの結果を見る前に、安全重視の合格基準を固定した。その後、適格な2 category・4 caseへ適用した結果は `fail` だった。利用者指定で同じCSVを再利用したrequest v5のhealth-ready開発回帰では4件全てのstrict intent検証まで改善したが、評価用後処理で停止した。段階診断付き部分再計測はdataset全体を完走していないため、新しいassessmentを生成していない。結果を見て修正した同じCSVは「開発回帰」であり、独立holdoutや未知データへの合格証拠ではない。元の評価reportは `not_assessed` のままである。
- 2026-09-07の利用者判断で画像の未知データ評価を再開した。初回は正例2・負例2で不適格だった。後続のcategory-only検索ではCDP送信前遮断により外部到達を100件へ固定し、追加70件を遮断、候補10件を「黒い本体の電気ケトル」の正例4・負例6へCLIP前に固定した。候補を送らないgpt-image 4 calls・retry 0の独立参照と固定ONNXでは、正例中央値0.924253657、負例中央値0.870871561、pairwise AUC 1.0、参照pHash最小距離12で単一条件の事前基準を満たした。続く未使用の「黒いメッシュ背もたれ・ヘッドレスト付きオフィスチェア」は正例4・負例6・曖昧2へ事前固定したが、正例中央値0.900518905、負例中央値0.921669262、AUC 0.291666667で `fail` だった。適格な2条件で結果を再現できていないため画像rankingは無効のままとする。
- 正常完了した検索結果と承認内容を再確認し、型付き条件の必須状態と判定から、内部の点数、証拠、外部サービス情報、郵便番号などを除いた表示データへ変換できる。0件も履歴へ保存し、失敗結果は保存しない。同じ保存をやり直しても外部検索やランキングは再実行しない。ローカルSQLite version 2での30日保存、一覧、詳細、参考画像取得、個別削除、期限削除まで合成データで確認済みである。旧version 1 DBは変更せず拒否する。local APIは暫定schema 5.0履歴詳細だけを取得し、version 2の一覧・画像・削除、認証、現在の画面には未接続である。
- ローカル専用の検索job基盤へ、最終承認済み検索からOutscraper 1 task、最大24商品画像、固定CLIP、暫定ranking v5、schema 5.0履歴までを実行するproduction backend callbackを接続した。同じ承認bindingの二重投入は既存jobを返し、job DBには検索文、商品、approval token、provider本文、生例外を保存しない。fixtureによるoffline E2Eで履歴の再読込まで確認し、job投入・状態取得・取消・schema 5.0履歴詳細取得のlocal ASGI API factoryも追加した。server起動構成、最終承認controller、現行・次期UIとは未接続である。
- Markdown参照検査の定型化と、動作へ接続されていなかった `APP_ENV`・`LOG_LEVEL` の削除まで完了し、未完了の小規模タスクはない。旧環境値は無視され、ログ制御が追加されたことは意味しない。
- 次期フロントエンドはこのリポジトリで自前開発する。納品待ちを解除し、今回の文書更新に続く作業として設計・実装・ローカルAPI接続を管理する。
- 本番運用にはper-user・session・day・costの利用量quotaを設けない。Bonsai 1 call、Cloudflare先行1 callとその明示了承後の `4 + N` calls（Nは視覚条件1〜3件）、先行画像の作り直しは1回まで、Outscraper task 1回、候補・画像・poll・byte・timeout上限、自動retryなし、明示承認は操作契約として維持する。実サービス確認は送信内容、回数、想定費用と「費用上限なし」を事前に示し、利用者の承認を得てから別に行う。

## 今回の処理が本番で当たる場所

```text
検索条件を入力
  -> 「条件を整理する」を実行
  -> [Bonsaiを1回呼ぶ -> JSON生成を制約 -> 完全schemaでstrict検証]
  -> 整理済み条件を確認
  -> 画像を使う場合：参考画像1枚を生成して確認
  -> 了承後に条件別の偽画像だけを生成し、参考画像と合わせて確認
  -> 商品検索の最終確認
  -> 商品を取得・順位付け
  -> 結果表示・履歴
```

Bonsaiが走るのは、1回の検索全体ではなく、1回の「条件を整理する」操作につき1回である。同じ整理済み条件の承認、商品取得、結果の再表示、履歴閲覧では追加呼出ししない。利用者が条件を編集して再度「条件を整理する」を実行した場合は、新しい整理処理としてもう1回呼ぶ。失敗時の自動retryは行わない。なお、この設計は `src/search_v2/` の独立したバックエンド境界であり、現行画面や自前開発する次期フロントエンドにはまだ接続していない。

## 残っている作業

| 順番 | 作業 | 利用者側で用意するもの |
|---|---|---|
| 完了 | DNS部品、画像取得部品、起動時の許可配信元をproxy serviceへまとめた。 | 合成設定だけで完了したため、利用者側の準備は不要だった。 |
| 完了 | Windows 11 / WSL向けに、名前解決の5秒application deadlineと `spawn` process isolationを追加した。 | 下記4の情報を受領した。実host通信とWindows native確認はまだ行っていない。 |
| 完了 | 固定CLIPのCPU実行、process隔離、単一検索条件31枚の自己参照なしcharacterizationを完了した。事前AUC基準は未達だった。 | 下記6のnear 13枚・far 18枚を受領した。追加準備は不要。 |
| 完了 | far 18枚を色・接続方式・ゲーミング用途・対象種別へ対応付け、属性別のscore傾向を固定した。 | 利用者からf1〜f18の属性を受領した。 |
| 完了 | near 13枚を目視し、確認できる属性と用途不明のn5・n6を分けて固定した。 | 利用者側の追加準備なしで完了した。 |
| 完了 | 通常ランキングへ、平均4.0以上と総レビュー件数から作る補助評価を唯一の最小base weight 0.05で追加した。 | 利用者側の追加準備なしで完了した。星別件数やレビュー本文は使っていない。 |
| 完了 | 画像scoreを視覚的特徴だけの補助評価とし、有線・無線を商品名・構造化属性へ分離した。全体保持前処理でcase1の接続方式非依存AUC 0.928571429を再固定した。 | 利用者側の追加準備なしで完了した。元のnear/far AUCは0.759259259で未達である。 |
| 完了 | case2の11候補と期待順位を固定し、全体保持前処理で自己参照を除くCLIP cluster診断とレビュー品質の同条件tie-breakを再確認した。 | case2一式を受領した。AUC 0.642857143、期待順位一致27/53だが、独立4方向参照がないため正式評価ではない。 |
| 完了 | CLIP入力を中央切り抜きから、縦横比を維持して画像全体をモデル平均余白内へ収める方式へ変更した。 | 利用者がcase1低下とのtrade-offを確認して採用した。 |
| 完了 | case3の20候補と期待順位を固定し、自己参照を除くCLIP cluster診断を再現した。 | case3一式を受領した。AUC 0.468750000、期待順位一致80/173で、画像だけでは分離できなかった。 |
| 完了 | 型付き条件、trusted registry、条件ごとの証拠裁定、必須状態を先に扱う順位、生成画像と候補画像の比較方法を設計した。 | 利用者側の追加準備なしで完了した。production codeとranking profileは変更していない。 |
| 完了 | 型付き条件とtrusted registryの最小domain modelをoffline TDDで実装し、typedな合成証拠によるunknown・conflict・順位安定性を確認した。 | 利用者側の準備なしで完了した。現行pipelineとranking profileは変更していない。 |
| 完了 | 現行の観測済み商品属性と限定した商品名表現を、registryが許可する `structured`・`title_exact` 証拠へ変換するadapterをoffline TDDした。 | 利用者側の準備なしで完了した。説明文・画像・LLMは使わず、現行pipelineとrankingには接続していない。 |
| 完了 | Bonsaiのstrict応答へ型付き条件候補を追加し、trusted registryが受理できる候補だけを確定するadapterをoffline TDDした。未知key、値・型・単位不整合、hard指定できないsemantic条件、重複は確認待ちにする。 | 利用者側の準備なしで完了した。固定した合成応答fixtureだけを使い、Bonsai serverやモデルは起動していない。 |
| 完了 | 型付き条件、商品証拠、条件ごとの裁定、`typed_product_sort_key()` を独立したranking v4へ接続し、必須状態を総合scoreより先にした。旧cache・履歴をv4として読み替えない。 | 利用者側の準備なしで、合成intent・商品fixtureだけを使って完了した。 |
| 完了 | ranking v4を第1確認、承認、state、検索後半のoffline pipeline、表示用履歴へschema 3.0 / 2.0で接続した。旧v3 artifactとSQLite version 1は暗黙変換しない。 | 利用者側の準備なしで、合成応答・商品・state・履歴fixtureだけを使って完了した。 |
| 完了 | case1〜case3を設計用development setとして固定したまま、未使用holdoutの正解・予測を分離し、条件・裁定・順位を集計するoffline評価契約を実装した。 | 利用者側の準備なしで、合成fixtureだけを使って完了した。実データの品質はまだ評価していない。 |
| 完了 | 実holdoutの結果を見る前に、安全重視の品質基準を固定policyとdigestへ記録し、独立assessmentを実装した。 | 利用者が全category必須、category別安全label必須、通常decision accuracy 0.90を選択した。APIキーや実データは使っていない。 |
| 完了 | 固定済みの合格基準で最初の未使用holdoutを評価した。構成は適格だったが、Bonsai strict応答失敗4件を除外せず `fail` とした。 | 受領済みCSVとlocal Bonsaiを使用した。以後このCSVを使う結果はdevelopment regressionとして扱う。 |
| 完了 | Bonsai requestへ `json_object` 宣言を追加し、`max_tokens` を削除した。本文非保持の6段階diagnosticを追加し、strict検証は維持した。 | 同じCSVの4件を再実行したが、全件が300秒で `request_failed` となった。新しいデータは不要だった。 |
| 完了 | Bonsai request v4から生成token上限とHTTP timeoutの公開設定を削除した。response 1 MiB上限、retry禁止、strict parserは維持した。 | 利用者側の追加準備なしでoffline TDDと関連回帰を完了した。 |
| 完了 | 同じCSVの4 caseをlocalhost Bonsaiへ各1回、時間上限なし・retryなしで再実行した。 | 全件で応答は完了したが、4件とも `content_not_json` でranking前に失敗した。結果はdevelopment regressionであり、独立holdout合格ではない。 |
| 完了 | llama.cppが生成grammarへ変換できる非空のJSON schemaをBonsai request v5へ追加し、application側の完全なcanonical schemaによるstrict検証を維持した。 | 新しいCSV、画像、APIキーなしで、offline testとlocal converter検査を完了した。local modelは実行していない。 |
| 完了 | `/health=200` を確認してからrequest v5をlocalhost Bonsaiへ送り、JSON制約が実推論でも機能するかdevelopment regressionとして確認した。 | 同じCSVを4 callsで再利用した。全件でstrict intentは通過したが、評価用後処理で停止した。 |
| 完了 | raw本文を残さない後処理段階診断とquery-less blocking投影を固定し、次回はtyped proposal・query plan・typed ranking・prediction projectionのどこで止まったか区別できるようにした。 | 新しいデータ、画像、APIキー、model callなしで完了した。 |
| 完了 | 段階診断付き再計測を途中で停止し、非blocking intentの検索可能性contractをofflineで修正した。 | 2件完了後、利用者の「全体で1件だけ」という訂正に従い3件目を中断し、4件目は送信していない。追加データは使っていない。 |
| 完了 | 更新promptと受理前検査を、同じ使用済みCSVの先頭1件・合計1 callだけで確認した。 | 新しいデータ・画像・APIキーは使っていない。HTTP応答後に受理前で停止した。 |
| 完了 | 原因別diagnosticで同じ先頭1件を合計1 callだけ再確認した。 | HTTP 200後の `draft_schema_invalid` で停止した。新しいデータ・画像・APIキーは使っていない。 |
| 完了 | 生成schemaと完全schemaの既知差分を閉じ、draft schema失敗を固定groupへ分類できるようにした。 | 互換regex、価格9 variant、本文非保持groupをofflineで検証した。実modelは再実行していない。 |
| 完了 | EXEC-051の新生成schemaを同じ先頭1件・合計1 callだけで確認した。 | 完全draft schemaと正規化を通過し、`intent_searchability_invalid` で停止した。2件目、retry、assessmentはない。 |
| 完了 | 通常の商品種別または全blocking確認待ちを生成時に必須とし、検索不能を安全な固定groupへ分けた。 | 新しいデータ・画像・APIキー・model callなしでoffline実装とconverter検査を完了した。 |
| 完了 | 商品種別またはblocking確認待ちを強制する生成schemaで、同じ先頭1件を合計1 callだけ再確認した。 | strict intentとtyped proposal生成まで成功し、`blocking` で停止した。新しいデータ・画像・APIキーは使っていない。 |
| 完了 | queryなしのblocking proposalを商品取得前の専用第1確認へ返し、Cloudflare・Outscraperへ進ませないorchestrator境界をofflineで実装した。 | 利用者側の準備なしで完了した。追加CSV、画像、APIキー、model callは使っていない。 |
| 完了 | Bonsai request v6で完全schema本文の二重送信を除去し、本番起動例へprompt cache、context 8,192、parallel 1を明示した。 | 4,096は最大入力契約を満たさないため採用しない。i5-13600KF CPU版の1-token prompt benchmarkはwarm時約115倍だったが、full JSONとCore Ultraは未確認。Vulkan buildは現行build完成後の別工程とする。 |
| 完了 | request v6とprompt cacheを同時に使うlocalhost Bonsai結合testを追加し、明示承認後に実model 2 callsを完走した。 | 2件ともfull JSON・strict intentに成功し、2件目で891 cached tokensを確認した。Core Ultraでの速度は別途実機確認が必要。 |
| 完了 | 同じ固定request v6を2回だけ送り、prompt cache処理時間とcompletion生成時間を分離する専用診断を実行した。 | Core i5-13600KFではprompt処理353.47倍、wall全体1.52倍。warm wallの99.82%は生成であり、Core Ultraでは別途実機確認する。 |
| 完了 | request v7のcompact wire、完全19-field復元、sparse価格schema、minified出力指示をoffline TDDした。 | 代表fixtureは126 Bonsai tokensで196以下。生成token上限は設けず、実model・Core Ultraの速度と品質は新しい明示承認後に確認する。 |
| 完了 | request v8でcompact schema自体の文字列長、配列数、root field profileを構造的に制限し、typed attributeとvalue typeの不整合も生成schemaとadapterで拒否する。 | 入力根拠検査、明示JPY上下限、SudachiPy形態素spanによる除外対象の復元を実装した。修正後の承認済み単一fixtureは全固定判定に成功した。Core Ultraと未知入力全般は未確認。 |
| 完了 | SudachiPy source-grounding修正後の固定合成入力をlocalhost Bonsaiへ1回だけ再送し、意味条件を確認した。 | 83.398秒で完了し、未知語、価格範囲、除外、二重否定、ready proposal、query planの全判定が成功した。Core Ultra、未知入力全般、実商品検索は未確認。 |
| 完了 | local単一processの検索job repositoryとworkerを実装した。同時実行1件、重複防止、状態照会、取消、開始期限、再起動回復、30日保持を一時SQLiteと注入callbackで確認した。 | 利用者が「ローカル専用」と決定した。追加データ、画像、APIキー、model callは不要だった。 |
| 完了 | [EXEC-066](docs/GOAL.md#exec-066-counterfactual-v4の暫定本番実装) は、accuracy 0.875の既知制約をprofileへ固定し、Cloudflare exact `1 + N`、永続single-use人間承認、現行 `IntentReview` からのversion分岐、商品画像proxy・固定CLIP、ranking v5、別schema 5.0履歴までを実装した。 | offline E2Eと固定CLIP runtimeを確認済み。実Cloudflare等のlive検証は別の事前説明と明示承認後に行う。 |
| 完了 | [EXEC-075](docs/GOAL.md#exec-075-暫定本番検索のjob履歴接続と無quota方針) で、最終承認済み検索をlocal job、Outscraper、商品画像、固定CLIP、ranking v5、履歴locatorへ接続した。 | 本番quotaは設けず利用量を記録する。fixtureによるoffline E2Eまで完了し、実通信・API・UIは行っていない。 |
| 完了 | [EXEC-076](docs/GOAL.md#exec-076-local検索job履歴http-api) でjob投入・状態取得・取消・schema 5.0履歴詳細取得のlocal ASGI API factoryを追加した。 | 15分以内のin-memory capability、固定local owner、loopback限定、表示projection、固定errorをoffline ASGI testで確認した。server起動、最終承認controller、UI、実通信は未実施である。 |
| 後続作業 | [SEARCH-FLOW.md](SEARCH-FLOW.md) に基づいて次期画面を自前で設計・実装し、合成データで操作を確認した後、ローカルAPIへ接続する。 | 外部納品物は不要。React + StyleXを使い、共通ボタン寸法・配置先・起動手順・API契約を整理する。実サービス検証の承認は別途必要。 |
| 最後 | ブラウザ操作、実サービス、障害時の動き、配布方法を順に確認する。 | 下記の10～11が必要。実サービス確認は毎回、送信内容、回数、想定費用、費用上限を設けないことを示して承認を得る。 |

### 完了したrequest v4のlocal-only再実行

- 接続先: `http://127.0.0.1:18080/v1/chat/completions`
- 操作: repository内の同じCSVにある4つの検索文をlocal Bonsaiへ各1回送る。retryは0、合計4 calls
- payload: 固定system prompt、canonical schema、検索文、`response_format={"type":"json_object"}`。`max_tokens`、商品名、商品属性、URL、ASIN相当値、画像は送らない
- 上限: application側の時間上限と生成token上限は設けない。response 1 MiB、server context 8,192、parallel 1は維持し、llama.cppのcontextとEOSは残る
- 停止: 応答完了、接続・OS失敗、server context境界、EOS、または人間がrunnerとserverを `Ctrl+C` で停止するまで待機し得る。自動retryは行わない
- credential・費用・network: credentialなし、費用0円、外部networkなし、localhostだけ
- 保存: server logとprompt cacheを無効にし、生responseと検索文を保存しない。digest、固定status、安全なdiagnostic、集計値だけを残し、終了後serverを停止する
- 結果の位置付け: 使用済みCSVによるdevelopment regression。独立holdout、未知データの一般化、production E2Eとは扱わない
- 実結果: 4件ともHTTP応答完了。所要時間は313.169秒、316.069秒、325.651秒、318.563秒。全件が `finish_reason=stop`、completion 2,000 tokens、約9.2 KiB、`content_not_json` で失敗した
- 評価: coverageは適格、failed 4、ranked 0、元reportは `not_assessed`、固定assessmentは53 checks中45件未達の `fail`
- 後処理: serverを停止し、`127.0.0.1:18080` の非listenと `llama-server` process終了を確認した

### request v5初回実行で判明した起動条件

- 送信前検査: request schema 5.0、非空生成schema、固定model・CSV、4 body、`max_tokens`・timeout不在は成功した
- 実結果: 4要求を逐次各1回送ったが、各0.006〜0.010秒で全て `request_failed`、response 0 bytes、completion token不明だった。推論、strict intent、typed proposal、rankingには到達していない
- 原因: llama.cppはmodel loadより先にHTTP portをlistenする。初回runnerはport listenだけを待ったためmodel ready前に送信した。同じ条件のhealth-only確認では `/health` がlisten直後503、2秒後200となった
- 評価: failed 4を除外せず、coverage適格、ranked 0、元report `not_assessed`、assessment `fail` とした。これは生成schemaまたはranking品質の評価ではない
- 次回条件: processとportに加えて `/health=200` を確認してから4要求を送る。自動retryはせず、新しい明示承認を得る
- 後処理: serverを停止し、port非listenとprocess終了を確認した。一時runnerも削除した

### request v5のhealth-ready再実行結果

- 送信条件: 固定model・同じCSV・非空生成schema・4 bodyを再照合し、`/health=200` 後にlocalhostへ逐次4 calls、retry 0で送信した
- 実結果: 全件HTTP 200、`finish_reason=stop`、completion 143〜146 tokens、response 1,178〜1,189 bytesで完了した
- 改善確認: 4件ともstrict intent検証を通過した。request v4の `content_not_json` はこの4件では解消した
- 未完了: その後の評価用一時runnerで4件とも `postprocess_failed` となり、typed rankingは完了していない。failed 4を除外しないassessmentは `fail` だが、typed条件や順位品質の値ではない
- 切り分け: modelを呼ばない合成ready intentはrankingまで通った。合成blocking ambiguity intentはproposal後のquery plan生成で停止した。ただし実4件の個別失敗段階は保存しておらず、同じ原因とは断定しない
- 完了した準備: 本文非保持の4段階diagnosticを固定し、blocking ambiguityはquery plannerを呼ばずquery-less blocking予測へ投影できるようにした。過去4件の段階は復元していない
- 次の作業: 後続の部分再計測とoffline修正は次節のとおり。model callは自動実行しない
- 後処理: server停止、port非listen、`llama-server` processなし、一時runner削除を確認した

### 段階診断付き部分再計測とoffline修正

- 送信前検査: 固定model SHA-256 `284a335aa3fb2ced3b1b01fcb40b08aa783e3b70832767f0dd2e3fdfa134bd54`、CSV SHA-256 `b8cd685aae7251792700ce312c7ddc410c55e0bda5416abef68de83ce55429ea`、生成schema SHA-256 `f557081591fa9d322364e8b65ac0583ee78a0359cd7e1721b659491e1e2fa865`、request schema 5.0、`max_tokens`・timeout不在、`/health=200` を確認した
- 実結果: 1件目はHTTP 200、`finish_reason=stop`、146 tokens、1,189 bytes、151.339秒、2件目はHTTP 200、`finish_reason=stop`、144 tokens、1,186 bytes、118.616秒で、どちらもstrict intent後の `query_plan_invalid` だった
- 実行数訂正: 利用者の意図は「各caseを1回」ではなく「全体で1件だけ」だった。訂正時に3件目は送信済みだったため直ちに手動中断し、4件目は送信していない。3件目の応答・token・byte・評価値は確定していない
- 評価境界: 完走していない部分実行からdataset評価またはacceptance assessmentを生成していない。検索文、生response、正規化intent、商品情報、内部例外本文は保存していないため、完了2件の具体的なfield値と直接原因は復元できない
- offline再現: 有効なtyped conditionを持つが商品名・category・required・preferred検索語が全て空の非blocking intentは、proposalが `ready` になった後に `query_plan_invalid` となった。実2件と同一原因とは断定しない
- 修正: 非blocking responseはstrict受理前に既存query plannerで検索queryを構築できることを必須とした。promptにも商品種別または検索語を最低1つ入れ、検索fieldへURLを入れない規則を追加した。blocking ambiguityのquery-less投影は維持する
- 互換性: request schema 5.0、完全schema、生成schema、生成token上限なし、HTTP timeoutなし、response 1 MiB、retry 0は変更していない。prompt変更により次のbody・request digestは過去実行と異なる
- 後処理: server停止、port非listen、`llama-server` processなし、一時runner削除を確認した。訂正後の追加model callは行っていない

### 完了した更新promptのlocal-only 1件確認

- 接続先: `http://127.0.0.1:18080/v1/chat/completions`
- 送信前条件: 固定model・同じ使用済みCSVの先頭1件・request schema 5.0・非空生成schema・1 bodyを照合し、`/health=200` を確認する
- payload: 更新済み固定system prompt、完全schemaと互換生成schema、先頭caseの検索文だけ。商品名、商品属性、URL、ASIN相当値、画像は送らない
- 実行数: 全体で1 case・1 callだけ、retry 0。結果にかかわらず次caseや同一caseを自動実行しない
- 上限: application側の生成token上限とHTTP timeoutなし。response 1 MiB、server context 8,192、parallel 1は維持する
- credential・費用・network: credentialなし、費用0円、外部networkなし、localhostだけ
- 保存: 検索文、生response、正規化intent、商品情報、provider error、内部例外本文を保存しない。digest、固定status、列挙済みstage、所要時間、token数、response byte数だけを記録する。1件だけなのでdataset全体の品質assessmentは作らない
- 位置付け: 使用済みCSVによるdevelopment regressionであり、独立holdout、未知データの一般化、production E2Eではない
- 実結果: HTTP 200、`finish_reason=stop`、143 tokens、1,183 bytes、102.333秒で応答し、adapterの `intent_normalization_invalid` で受理前に停止した。transport callは合計1、retry 0で、2件目・同一case再試行・assessmentは実行していない
- 後処理: server停止、port非listen、`llama-server` processなし、一時runner削除を確認した

### 完了した原因別1件確認と次の生成schema

- 実行結果: `/health=200` 後に旧生成schemaの先頭 `mouse-01` を合計1 callだけ送信し、HTTP 200、`finish_reason=stop`、257 tokens、1,613 bytes、117.242秒、`draft_schema_invalid` となった
- 到達範囲: envelopeとcontent JSONには到達したが、完全draft schemaで停止した。正規化、検索可能性、typed proposal、rankingには到達していない
- 実行数: transport call 1、retry 0。2件目、同一caseの再試行、dataset assessmentは行っていない
- 後処理: server停止、port非listen、processなし、一時runner削除を確認した
- offline改善: ambiguity code patternを保持し、decimalを同値のconverter互換regexへ変換し、価格をmode・source別9 variantへした。draft不一致は本文や値なしの固定groupへ分類する
- 新生成schema: 11,051 bytes、SHA-256 `c8537ff3ee378b0ef57d41889210e1a807962d2cbd1ab8772020706481a58ca6`。同梱converterとoffline testは成功したが、実modelでは未確認
- 利用者側の準備: 新しいCSV、画像、APIキーは不要
- 承認: 今回の1 callは消費済みである。新生成schemaを同じ先頭caseで確認する場合も、endpoint、payload、回数、保存範囲を再提示した新しい明示承認が必要

### 完了した新生成schemaのlocal-only 1件確認

- 送信条件: 固定model、使用済みCSVの先頭1件、更新prompt、完全schema、EXEC-051の生成schema、request schema 5.0を照合し、`/health=200` 後にlocalhostへ合計1 callだけ送信した
- 上限と保存: retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB。検索文、生response、正規化intent、商品情報、URL、ASIN相当値、provider error、validation本文は保存・転記していない
- 実結果: HTTP 200、`finish_reason=stop`、143 tokens、1,187 bytes、252.845秒で、完全draft schemaと正規化後の `intent_searchability_invalid` となった
- 実行数と後処理: transport call 1、2件目・同一case retry・dataset assessmentなし。server停止、port非listen、process終了、一時runner削除を確認した
- offline改善: 通常経路は `product_name_ja` の商品種別、商品種別を安全に確定できない経路は1件以上の全blocking ambiguityを生成時に必須とした。検索不能は値を保持せず `missing_terms`・`invalid_terms` に分ける
- 次schema: 16,663 bytes、SHA-256 `2e5cfed749d4f71898c42226c58e3f838664cac0e66f1c3230e54daf384f004d`。この時点ではllama.cpp同梱converterとoffline testだけが成功しており、後続のEXEC-053で実modelへ送信した
- 利用者側の準備: この時点では新しいCSV、画像、APIキーは不要で、後続の1 call確認に対する別の明示承認だけが必要だった

### 完了した生成時検索可能性schemaのlocal-only 1件確認

- 送信条件: 固定model、使用済みCSVの先頭1件、更新prompt、完全schema、16,663 bytesの生成schema、request schema 5.0を照合し、`/health=200` 後にlocalhostへ合計1 callだけ送信した
- 上限と保存: retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB。検索文、生response、正規化intent、typed condition、商品情報、URL、ASIN相当値、provider error、validation本文は保存・転記していない
- 実結果: HTTP 200、`finish_reason=stop`、473 completion tokens、2,508 response bytes、395.713秒。strict intentとtyped proposal生成まで成功し、proposalは `blocking` となった
- 実行数と後処理: transport call 1、2件目・同一case retry・dataset assessment・商品取得・rankingなし。server停止、port非listen、process終了、一時runner削除を確認した
- 判断: queryなしで利用者確認へ止めるべき応答を得たが、blocking理由の本文は保持していない。EXEC-053時点ではorchestratorがquery planをproposalより先に要求していたため、後続のEXEC-054でこの状態を専用第1確認へ返すoffline接続を実装した
- 利用者側の準備: 次のoffline作業には追加CSV、画像、APIキー、model call承認は不要

### 完了したquery-less blocking第1確認のlocal-only 1件結合確認

- 送信条件: 固定model、使用済みCSVの先頭1件、固定prompt、完全schema、16,663 bytesの生成schema、request schema 5.0、現行orchestratorを照合し、`/health=200` 後にlocalhostへ合計1 callだけ送信した
- 上限と保存: retry 0、application生成token上限・HTTP timeoutなし、response 1 MiB。検索文、生response、正規化intent、typed condition、ambiguity・issue本文、商品情報は保存・転記していない
- 実結果: 233.419秒、HTTP 200、2,508 response bytes、transport call 1、Bonsai利用量 `succeeded`。typed statusは `blocking`、確認型は `BlockingIntentReview`、query planとquery digestは存在しなかった
- 実行範囲: 2件目、同一case retry、dataset report・assessment、Cloudflare・Outscraperの予約・call、商品取得、rankingなし。server停止、port非listen、process終了、一時runner削除を確認した
- 判断: query-less blockingの実応答を専用第1確認へ返す結合は確認できた。blocking理由・妥当性、検索成功、条件分解・商品順位品質、未知データへの一般化は未確認である
- 利用者側の準備: このEXEC-055完了時点では追加dataやmodel callを行わない判断だった。2026-09-07に画像評価を再開したため、現在の再開位置は本書末尾を正とする

## 後で必要になるもの

最初の本評価はBonsai strict応答失敗によりranking前に `fail` となった。その後、request v8、SudachiPy source grounding、承認済みlocalhost再確認、単一Outscraper taskまで進み、2026-09-07に画像の未知データ評価も再開した。EXEC-064の適格category-only 2条件は1 pass・1 failとなり、固定失敗artifactのcrop・contrastive・centroidも全て基準未達だった。EXEC-065では、未知の視覚条件を正規化済み元入力spanへ結び、desired anchor 1枚と条件違反 `N` 枚で条件別marginを作るstrict domainを実装した。承認済みのテスト用gpt-image 6 calls、retry 0でdevelopment参照を生成して固定ONNX較正したが、適格条件pool AUC 0.78で不合格だった。診断閾値は採用せず、独立評価へ進んでいない。フロントエンドは自前開発の後続工程で接続する。APIキーや商品URLはチャットへ共有しない。

1. 受領・起動確認済み: `/home/products/models/Bonsai-8B.gguf` を `/home/llama.cpp/build/bin/llama-server` からCPUで起動できる。EXEC-055のlocalhost限定確認は先頭1件・合計1 callだけ完了し、query plan・query digestなしの `BlockingIntentReview` まで到達した。追加model callの予定はない
2. 本番Cloudflare画像生成の利用アカウントとcredential、Outscraperの利用アカウント。gpt-imageはテスト専用であり、製品adapterへ移行しない
3. サービスごとのAPIキー。本番のper-user・session・day・cost quotaは設けない。操作ごとの固定call数、候補・poll・byte・timeout上限、自動retryなしは維持する
4. 受領済み: Windows 11 / WSL、Intel Core Ultra 9 288V。DNS境界はCPUだけで動く。CLIPも最初はCPU優先とし、GPU・NPU利用を希望する場合だけ対応可否と共有メモリ量を追加確認する
5. 受領・配置済み: 固定CLIP modelはrepository内の `models/clip-vit-base-patch32-12b36594/` に3つの読取専用ONNX関連fileとして配置した。CPU用ONNX Runtime 1.23.2もlock済みで、合成画像によるlocal-only実推論に成功した。`/home/products/models/Bonsai-8B.gguf` は別用途のBonsai用である。CLIP modelのGit追跡・push・配布方法は未決定
6. 受領・確認済み: 検索条件は「黒い無線ゲーミングマウス」、許可hostはexact `m.media-amazon.com`。`tests/img/case1/near/` 13枚と `tests/img/case1/far/` 18枚を固定hashのPNGとして受領した。全体保持前処理の自己参照なし評価はpairwise AUC 0.759259259で事前基準0.80へ未達だった。接続方式を画像評価から外し、f2・f4・f7・f10を画像上の正例へ移した補助評価はAUC 0.928571429だった。f1〜f18の色、接続方式、ゲーミング用途、対象種別も受領・固定済みである
7. 確認済み: n1〜n13はlocal画像から目視できる範囲で属性を固定した。全て黒いマウス、n1〜n4とn7〜n13はゲーミング、n5・n6はゲーミング用途不明とした。接続方式は静止画像から確定せず、全13枚を不明としている。商品名、構造化属性、商品ページによる仕様確認はまだ行っていない
8. 確認済み: 現在はローカル専用、単一host・単一process・worker 1本とする。将来公開・複数利用者へ変更する場合だけ、認証方法、保存先、backup、削除、複数workerの方針を別途決める
9. 外部委託先からの納品一式は不要。次期フロントエンドのソース、素材、依存関係の固定ファイル、ビルド・起動手順、設定名、API契約、既知の問題は自前開発の成果物として整備する。秘密情報の実値は含めない
10. 未知データで独立した最終採否を行うには、development相対合格したbatch較正付きminimum-positive v4に対し、最低2 category・各2 case・各3商品・各1 exact条件、各categoryにhard contradictionとuncertaintyを最低1 labelずつ持つdatasetを完了する。未使用のデスクライト・クランプ条件による1 caseはaccuracy 0.875で不合格だったため、式や閾値の再調整へ流用せず固定する。残りはcase1からcase3、2026-09-05のCSV、EXEC-064・EXEC-065と今回caseの全条件を除外する。取得・生成前にdataset、label規則、合格基準、単一class・outlier・候補構成変化、失敗・欠損の扱いを固定する。本番Cloudflare評価はgpt-image評価と別の未使用holdoutで行う
11. 公開する場合は、配布先のサーバー、ドメイン、HTTPS化に必要な証明書などの運用環境

APIキーなどの秘密情報は、このMarkdown、チャット、Issue、Gitへ書かず、ローカルの秘密管理機能へ保存する。

## 別に残っている作業

AIレビューハーネスには、OpenAIを使う実サービス確認と、承認記録を長期保存する運用設計が残っている。これは商品検索の次の実装を妨げない。実行する場合だけ、OpenAIの認証情報、費用上限、外部送信の承認、保存・バックアップ方針が必要になる。

## 次の再開位置

DNS・固定ONNX・case1からcase3・typed-ranking-v4・holdout契約・Bonsai request v8・SudachiPy source grounding・単一Outscraper taskまで完了し、`EXEC-064` で実ブラウザ候補とgpt-image独立参照による初回画像E2E診断も完了した。次期フロントエンドは自前開発する。後続作業では画面設計・API契約を整理して実装へ進む。

EXEC-066の暫定production backendは完了し、EXEC-071では固定1条件のCloudflare desired・counterfactualをexact 2 calls、retry 0で実生成した。EXEC-072は、OutscraperとCloudflareを再実行せず、隔離Chromiumで値非表示取得したexact `m.media-amazon.com` URLへproduction proxyで1 GETし、その実商品画像と既存参照2枚を固定local CLIPへ通す限定liveまで成功した。結果は1 GET、retry 0、CLIP 3画像、3.440秒、normalized margin 0.570058732で、白い無地のマグ画像を0600 PNGへ保存した。これはOutscraper本番統合ではない。

EXEC-073では、成功済みOutscraper 1 taskの実行結果から商品情報と最大24件の先頭画像URLを正規化し、承認済み参照、production proxy、固定CLIP、batch較正、暫定ranking v5へ渡すoffline統合backendを追加した。EXEC-074の修正後liveでは、Cloudflare 2 calls、Outscraper 1 task・poll 9回、24商品の正規化、Amazon画像24件の取得、固定CLIP 7 batches、暫定ranking v5をretry 0のまま357.95秒で完了した。EXEC-075では、本番quotaを設けない明示policyと、最終承認済み検索をlocal jobからこの後半経路へ渡し、成功時だけschema 5.0履歴locatorを保存するapplication serviceを追加した。fixture E2Eは重複投入時も外部task相当を1回だけ実行して履歴を再読込できる。次期画面の自前開発では、最終承認controller・server起動構成とAPI・状態表示・取消操作を接続する。新application serviceを含む実サービスE2Eは、別の条件提示と明示承認後に行う。deployは未実施である。

詳細な進行状況は [docs/GOAL.md](docs/GOAL.md)、未解決課題は [docs/ISSUES.md](docs/ISSUES.md) を参照する。

最新の [EXEC-094](docs/GOAL.md#exec-094-省略された仕様名の推論を改善する) では、形状詞を含む属性名の誤拒否と、不適切な推論名の受理を修正した。共通属性の例による本番要求の比較は既知7例中2→3件の合格。未使用2例の初回は0/2で、解析修正後の1例も名前の基準は未達だった。全体offline2322件は成功したが、意味品質の改善は引き続き必要。今回の41実応答はrepository外へ永続保存した。次は観測済み16例への当てはめを避けて仕様名の意味推論を改善し、独立入力で評価する。全検索・順位監査は未再開。

EXEC-094継続では生成・受信の名称制約を整合し、offline2352件と実grammar84例が成功した。一方、本番要求の観測済み9例は3/9で意味精度は改善していない。診断2方式も各0/3のため不採用。追加15応答は別の永続private logへ保存済み。形式を満たしても意味が誤る問題が残り、全検索・順位監査は引き続き未再開である。


[EXEC-095](docs/GOAL.md#exec-095-仕様定義を与えたbonsaiの属性同定を検証する) でRAG前提の定義参照を実測した。候補名/単位のみ7/12から、正しい定義追加で11/12へ改善したが、資料不足/曖昧16件は全て誤選択し、進行基準は未達。全52応答を永続private logへ保存済み。次は定義を読む側の比較・追加学習などによる属性識別と保留能力の改善を検討する。検索器・RAG本番接続・全検索・rankingは未実施である。

[EXEC-096](docs/GOAL.md#exec-096-属性同定の保留をアプリケーションで強制する) では、数値属性の推論候補と実行条件を分離した。原文に属性名と数量の対応がなければアプリ側で保留し、一般的な了承では解除できない。旧52応答の再生は保留必須16/16、自動確定は正例0/36。保留の安全性を改善した一方、言い換えの自動同定は制限される。次は意味からの対応を独立に検証できる根拠と資料取得契約を設計・評価する。モデルの自己申告やconfidenceによる解除、旧採点の緩和は行わない。

[EXEC-102](docs/GOAL.md#exec-102-candidate経路の実画像付き実行) では新candidate専用の対話実テスト入口を準備済み（全体offline 2608件成功、実サービス未実行）。次は固定合成入力1件について実行条件の承認を得て、実参考画像→人間確認→偽画像→人間確認→商品取得→Bonsai/CLIP→履歴再読込を行う。旧入口の実成功や専用入口のoffline成功を新経路の実成功として扱わない。

EXEC-102の承認済み実行はBonsai 1 call・HTTP200後、視覚条件処理で停止した。画像生成/商品検索/CLIPは0回、履歴0件。応答本文は保存しておらず拒否の詳細分岐は未特定。固定codeの構造化diagnosticを追加し、関連151件のoffline確認が成功した。次はこの診断を使い、別途条件提示した実検証を行う。詳細は [WORKLOG 144](docs/WORKLOG.md#144-新candidate実テストは視覚条件処理で停止2026-09-10)。

診断付き実Bonsai再検証で原因を特定した。モデルが商品種別・外観・価格の全3節を視覚条件として選び、価格節でclause_scopeとなった。要求schemaにも価格節が候補として入っていた。次は既存の条件抽出と視覚候補の契約を接続し、数量/価格等を生成候補から外す設計を修正する。実測は1 call・retry0、画像/商品/CLIPは未実行。[WORKLOG 146](docs/WORKLOG.md#146-実bonsaiの視覚条件誤選択を診断2026-09-10)を参照。

視覚候補の生成契約を修正済み。既存の数量/価格/非視覚属性抽出と商品名詞句の確保を生成前へ接続し、同じ集合を要求schemaと受信検証で使う。名詞句が複数ならproduct_scopeで保留する。関連169件とローカルGBNF検証10ケースが成功。次は修正後の実Bonsaiと画像付きフローの再検証。[WORKLOG 147](docs/WORKLOG.md#147-非視覚条件を生成候補から除外2026-09-10)を参照。

修正後の実再検証では外観1件の抽出・参考画像/偽画像・人間の2段階確認・商品検索応答まで進んだ。商品評価用BonsaiのHTTP200後にranking_clip_history / unexpectedで停止し、商品画像/CLIP0、ranking未出力、履歴0件。次は意味評価parserとcomplete境界の固定code診断を整え、拒否の詳細分岐を保持する。追加liveは未実行。[WORKLOG 148](docs/WORKLOG.md#148-新candidate実テストは商品評価まで進行2026-09-10)を参照。

商品評価の詳細診断を追加済み。意味評価parser・rank・completeの3層で固定codeを保持し、18種類の不正応答を区別する。新規33件、関連222件、全体offline2716件成功。次は診断付き実行で商品評価の停止理由を確認する。今回の追加liveは0で、前回の本文未保存応答の原因を復元したものではない。[WORKLOG 149](docs/WORKLOG.md#149-商品評価の診断情報が失われる3層を修正2026-09-10)を参照。

診断付き実再開live-03でsemantic_field_bindingを特定した。Bonsaiの商品評価応答はJSON/stop/件数検証を通過したが、引用field_idの型または既存fieldへの所属で拒否された。生成schemaのfield_idが任意stringであるため、次は実在する同一商品のfieldへ引用生成を制約する。画像2枚と商品検索は成功、CLIP/ranking/履歴は未完了。再試行0。[WORKLOG 150](docs/WORKLOG.md#150-実商品評価の引用field束縛失敗を特定2026-09-10)を参照。

引用生成の制約を修正済み。商品index・実在field_idを同じschema分岐へ束縛し、文字位置上限と点数/引用の対応、空本文の保留を固定した。新規18件・関連184件、全体offline2734件、ローカル文法14ケース成功。次は修正後の実Bonsaiと全体フローの再確認。今回の実API/model callは0。[WORKLOG 151](docs/WORKLOG.md#151-引用の生成候補を同一商品の本文へ限定2026-09-10)を参照。

修正後の実再検証live-04は、参考/偽画像と商品検索に成功したが、商品評価の応答待ちで全体15分の期限に達した。引用生成修正の効果は未確認、商品画像/CLIP0、ranking/履歴未出力。次は画像確認待ち・検索待ちを含む段階別時間と実行期限の設計を見直す。今回は期限延長や再試行なし。[WORKLOG 152](docs/WORKLOG.md#152-引用生成修正後の実再検証は全体期限で停止2026-09-10)を参照。

実行時間対策として入出力をcompact wireへ変更し、本文・商品数・引用検証を維持した。24商品合成例の入力tokens約45%減、出力tokens約60%減。実runnerのwall・prompt/生成tokensと処理msの記録も追加。全体offline2749件成功。次は新wireで実Bonsaiの時間と品質を測定する。今回のモデル推論/外部送信は0で、実速度倍率は未確認。[WORKLOG 153](docs/WORKLOG.md#153-bonsai商品評価の入出力を圧縮し時間計測を追加2026-09-10)を参照。

外部APIなしの実Bonsai比較を実施した。旧形式は804.3秒でcontext上限による途中打ち切り、compactは205.5秒で24商品・96引用の構造検証を通過。ただしcompactは全商品0点・本文先頭1〜4文字の引用で、意味評価品質は不合格。正常結果同士の速度倍率は未確認で、品質維持を伴う高速化とは扱わない。次はこの意味評価不良の原因を切り分ける。実検索E2Eの完了は未確認。[WORKLOG 154](docs/WORKLOG.md#154-実bonsaiの時間比較でcompactの意味評価不良を確認2026-09-10)を参照。

後続の明示決定でBonsai商品採点を廃止し、CLIP用の視覚条件提案だけへ限定した。candidateの新採点は条件判定を優先し、タイトル単語一致80%＋CLIP20%（画像不明は単語一致のみ）。旧表示履歴は保持。関連309件、全体offline2755件成功。意味点数の高速化・修復は今後の対象とせず、次は新方式の実商品順位品質と全体フローを確認する。今回の実provider再実行は0。[WORKLOG 155](docs/WORKLOG.md#155-bonsaiをclip用の視覚条件提案だけへ限定2026-09-10)を参照。

最新の明示決定で、Bonsaiの役割へ検索語の言い換え・英訳候補作成を追加した。用途は視覚条件提案と語句候補作成の2つだけ。画像生成前に利用者が候補を確認して1 queryを選び、最大24件の検索へ反映する。商品採点には使わない。新規39件、関連356件、最終全体offline2794件成功。次は候補の同義性・英訳品質と、新方式の実検索・順位・所要時間を検証する。今回の実モデル・外部API実行は0。[WORKLOG 156](docs/WORKLOG.md#156-確認した検索語候補だけを検索へ反映2026-09-10)を参照。


実Bonsaiの2用途を合成6例・12 callsで確認したが、視覚意味2/6、語句意味1/6、両方合格0/6で基準未達。JSON受理だけでは品質を保証できない。希望・除外の取り違え、商品種別の一般化・英訳誤りに加え、Sudachiの商品名欠落も確認した。次は前処理と意味推論の改善を優先し、候補確認を維持する。全要求・応答と意味判定をprivate logへ保存済み。[WORKLOG 158](docs/WORKLOG.md#158-実bonsaiの2用途の推論品質は基準未達2026-09-10)を参照。


英訳を元語・各言い換えにそれぞれ1つ対応付ける形式へ変更した。未確定の訳はnullで保留し、確認後に最大8本から1本だけを検索へ使う。関連69件、全体offline2804件成功。新形式の実Bonsai品質は未測定であり、前回確認した意味品質不良・商品名欠落は引き続き改善対象。[WORKLOG 159](docs/WORKLOG.md#159-元語言い換えごとに英訳を1つ対応付け2026-09-10)を参照。


接尾辞を保持し、名刺入れが名刺へ欠落する前処理を修正済み。最終検索queryとBonsai商品句は名刺入れとなり、活用語＋接尾辞も元表記を保つ。関連145件・全体offline2820件成功。次は修正後の商品句と1語句1英訳の契約で実推論品質を再評価する。[WORKLOG 160](docs/WORKLOG.md#160-日本語接尾辞の欠落と語形の変形を修正2026-09-10)を参照。


LFM2.5-1.2B-JP Q6_Kの実比較を完了。既存llama.cppのSchema適用不整合は診断用--no-jinjaで回避できたが、既知6例の意味合格は視覚1/6・語句0/6。Bonsai2/6・1/6より改善せず、製品へは採用していない。CPU上の2用途中央値10.9秒・ピークRSS1.11GiBは軽量化の参考値で、同等品質やiGPU性能を示さない。次は意味品質を満たすモデル/推論方式の選定が必要。[WORKLOG 161](docs/WORKLOG.md#161-lfm25-12b-jpを実測し速度と品質を比較2026-09-10)を参照。


CLIPSeg＋MobileSAMの任意抽出器を実装し、既知4画像の平均IoU0.7016→0.9467と個体分離を確認した。次は残る取っ手混入、輪郭IoUと局所形状の意味の違い、未知カテゴリの精度、iGPU上の処理負荷を評価する。CPU4枚58.146秒・約1.35 GiBであり、本番採用や順位品質の合格は未確定。[WORKLOG179](docs/WORKLOG.md#179-mobilesamで個体分離と部位輪郭を改善2026-09-10)を参照。


形状条件ごとの測定と希望方向を候補確認/画像要求/順位/履歴へ接続した。側面の滑らかさを指定した既知2商品では順位逆転を解消し、参照差不足・逆方向は保留する。合成48組と全体offline3011件は成功。次は実Bonsaiの測定項目/方向解釈と、事前に基準を固定した未知実商品の評価。旧24商品の総合順位と実検索E2Eは未再実行。[WORKLOG180](docs/WORKLOG.md#180-意味に対応した形状特徴を実装比較2026-09-10)を参照。


全24商品の再評価を完了したが、目視順位一致43.2%→36.9%、nDCG@10 0.365→0.336で悪化した。直線も高く評価する滑らかさ指標を膨らみの代用にしないこと、微小な分離片による3件の保留を改善することが次の課題。旧データ/承認/履歴は保持し、今回の順位は診断出力として保存した。[WORKLOG181](docs/WORKLOG.md#181-全24商品の形状特徴付き総合順位を再評価2026-09-10)を参照。

膨らみ測定のオフライン実験では、同24商品の診断順位一致85.6%、明瞭な膨らみ3商品が上位3位、26maskの追加計算中央値0.149秒を確認した。ただし既存の参考差検査を保持すると全件保留となり、実フローの総合順位改善は未達。次は参考/偽画像の有効性と新測定値の誤差・閾値を検証し、独立商品で評価する。実験用測定器はproductionへ未統合。[WORKLOG182](docs/WORKLOG.md#182-膨らみ測定の識別力と追加時間をオフライン検証2026-09-10)を参照。

閾値の合成校正と別パラメータ検証は完了し、候補値0.010636を得た。ただし現在の参考対は変形後の最小差0.005680で安定性基準に不合格だったため、production閾値は変更していない。次は要求する意味を保つ参考画像対の改善と、実切出し誤差の検証。閾値を通すための更なる引下げは行わない。[WORKLOG183](docs/WORKLOG.md#183-膨らみ参照差の閾値を校正検証2026-09-10)を参照。

生成指示と参照品質検査を実装し、全体offline3021件が成功した。承認済み偽画像1件の実生成でも、変形後の最小差0.024392で既存0.02基準を通過した。生成7.715秒、ローカル切出し・検査48.444秒。次は新参照を用いる採点の整合性と全24商品のoffline診断、独立商品での評価。今回の参考対改善だけでは総合順位の改善を確定しない。[WORKLOG185](docs/WORKLOG.md#185-承認済み偽画像1枚を実生成し参照品質を検証2026-09-10)を参照。

新偽画像を使う全24件のoffline順位比較を完了。現行膨らみで63.1%、改良双方向膨らみで79.7%の順位一致となり、後者は強適合3件が上位3位。商品rankingへの改良測定接続は未実施。次は参照検査と採点の測定器を整合させ、固定した独立商品で再評価する。現在は母数不足・80%未達で正式合格ではない。[WORKLOG186](docs/WORKLOG.md#186-新偽画像で全24商品の順位を比較2026-09-10)を参照。

未知商品の取得・実画像テストを実施したが、正式合格は未確認。重複除外後20件に明瞭な膨らみ例がなく、構成不適格だった。改良測定でも上面のコーヒーを本体と取り違えて満点にするため、次は切出し対象部位・可視性の検証を優先する。単語点0の診断と、強適合を含む別データでの評価も残る。[WORKLOG188](docs/WORKLOG.md#188-未使用20商品の実画像で膨らみ評価を検証2026-09-10)を参照。


2026-09-10 EXEC-113更新: candidate既定は全体外観CLIP。部位抽出/専用形状測定の修正を新しい既定の必須作業とはしない。保存済み44件は全件採点できたが、以前24件の膨らみ順位が大きく低下した。次はカテゴリを跨ぐ未使用データで外観の近さと対象不在を評価し、採点範囲と品質を分けて判断する。汎用点を部位一致や条件充足確率にしない。全体外観へ部位補助点を混ぜる実装は、適用条件と有効性の検証前には追加しない。旧44件はdevelopment扱いを維持する。


2026-09-10 EXEC-114更新: SigLIP 2 Baseを保存済み44商品で実ローカル試験し、画像参照方式は現行CLIPより両集合で改善。条件文方式は片方で悪化した。製品コード/既存履歴は不変。次の候補は画像参照方式の独立adapter/profile接続と、未知カテゴリ・iGPUの別評価。試験結果を既存CLIP runtimeの値として保存せず、既知44件を新holdoutへ転用しない。

EXEC-115: SigLIP 2画像参照方式の未評価カップ21商品テストは目視順位一致75.8%（97/128対）で指定60%を達成。詳細は[WORKLOG192](docs/WORKLOG.md#192-siglip-2の未知商品21件で目視順位一致7582026-09-11)。この試験時点では本番組み込みは未実施だった。未知カテゴリ/独立人間評価/iGPU性能と総合順位の検証は別途残る。


EXEC-116（2026-09-11）: 利用者の組み込み指示によりcandidate backendの既定をSigLIP 2参考画像方式へ接続した。画像承認・ランキング・JSON/SQLite履歴のoffline回帰と全体3045件が成功。本番adapterの保存済み21商品は試験時と全点・順位が一致した。実行設定は[BACKEND](docs/BACKEND.md)を参照。旧CLIPは明示選択で保持。未知カテゴリ/独立人間評価/iGPU性能、実providerを含む再E2Eと次期frontendの接続は今回未実施。
