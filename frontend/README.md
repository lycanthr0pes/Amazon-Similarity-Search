# Amazon Explorer UI

自然文入力のローカルAPI接続画面は `?mode=connected` に追加しています。準備済み環境でbuild後、リポジトリ直下から `uv run --frozen --offline --no-sync python -m tools.browser_search_server --offline-fixture` を起動してください。8765番で合成応答による接続を試せます。実サービスの起動条件・回数上限は [BACKEND.md](../docs/BACKEND.md#ブラウザからの接続試験exec-124) を参照してください。入力は最大2000文字、画像生成前に文章を修正して最大2回再整理できます。画像の有無にかかわらず商品サムネイルと日英の点数内訳を表示し、商品名と優先・希望・否定条件を編集できます。fixtureは入力を保持しますが、条件・結果は固定合成です。以下は既定のモック画面の説明です。

永続履歴は `--history-db` で既存SQLiteを指定し、接続画面の `検索履歴` から開きます。検索せず履歴だけを復元する起動方法は `--history-only --history-db /absolute/private/history.sqlite3` です。一覧/詳細/再読込では商品取得・推論・画像生成を行いません。旧履歴に保存されていない商品サムネイルは表示できません。削除は確認ダイアログから実行できます。

接続画面のブラウザ検証はfrontendから `npm run test:e2e -- --config playwright.connected.config.ts`。この検証だけはPythonの準備済み環境とbuildが必要です。fixture serverを8766番で起動し、実providerを呼びません。

React + TypeScript + StyleXによるデスクトップ用オフラインモックです。任意の自然文入力、条件編集、任意の参考画像・比較画像確認、最終確認、5工程の商品調査、結果・検索履歴を操作できます。

表示する条件・商品12件・画像は固定の合成データです。入力を理解・検索せず、実バックエンド、Bonsai、外部API、認証情報を使いません。画像・Noto Sans JPもローカル配信します。編集した条件は確認画面へ反映しますが、固定の商品・比較結果は変えません。

Node.js 22.12以降を使用します。リポジトリルートからの初回準備と起動:

```sh
cd frontend
npm ci
npm run dev
```

開発画面は `http://127.0.0.1:5173/` です。依存取得は公開npmへの通信を行う環境準備です。準備後の画面利用はローカル配信だけで動作します。

開発画面が白紙のままの場合は、開発者ツールのNetworkで `/node_modules/.vite/deps/` が待機中になっていないか確認してください。2026-09-13には起動中Viteの依存準備待ちによる停止を確認し、開発サーバーの再起動で復旧しました。この症状では起動元ターミナルの `Ctrl+C` で停止し、同じ `frontend/` で `npm run dev` を実行してからブラウザを再読込します。


```sh
npm run check
npm test
npm run build
npm run preview
```

production buildの確認先は `http://127.0.0.1:4173/` です。ブラウザ検証は一度Chromiumを準備した後に行います。テスト自身が4173のpreviewを起動するため、手動previewは先に終了してください。

```sh
npx playwright install chromium
npm run test:e2e
```

GitHub Actionsの [CI](../.github/workflows/ci.yml) はpush・pull requestごとに独立したfrontendジョブを実行します。Node.js 22でnpm ci、型/整形、単体テスト、build、Chromiumのビルド版全テストと開発版のcontrols・motion・frame・navigationを確認します。ブラウザは1ワーカー・再試行なしで実行し、test.onlyを拒否します。依存とChromiumの準備は公開配布先へ通信しますが、画面テストは固定合成データとローカル配信のみを使います。

既定モックと接続画面は `src/ConnectedApp.tsx`、`src/ConnectedHistory.tsx`、`src/ConnectedProducts.tsx` の同じUIを使います。`src/App.tsx` は `search-client` にオフライン実装を注入する入口です。`offline-client.ts` が模擬段階遷移、`offline-history.ts` がタブ内履歴を担当し、旧 `history.ts` の保存データも読めます。`?mode=connected` だけ既存HTTP clientを使い、モックからAPIへ自動接続しません。

画像選択は最初の条件整理から反映します。後から画像を有効にすると再整理が必要です。準備は初回を含め3回、画像作成は準備ごとに初回を含め2セットまで。画像なしでも合成の商品画像を表示します。プロンプト編集と作り直しも操作できますが、画像は固定資材の再表示です。

履歴はこのタブで最大30件・30日間保持します。再読込すると検索フローは入力画面へ戻り、履歴は残ります。タブを閉じると履歴は消去されます。保存エラーでは結果を残して保存だけ再試行できます。検索文はブラウザ内に保存するため、UI確認には合成入力を使ってください。

回復表示はURLの `scenario` で確認できます。設定画面や実サービスへの切り替えはありません。失敗は各ページ起動で最初の1回だけ発生し、再試行を確認できます。

| URLの指定 | 表示 |
|---|---|
| `?scenario=empty` | 正常0件 |
| `?scenario=organize-error` | 条件整理失敗 |
| `?scenario=reference-error` | 参考画像失敗 |
| `?scenario=comparison-error` | 比較画像失敗 |
| `?scenario=research-error` | 商品調査失敗 |
| `?scenario=save-error` | 履歴保存失敗 |
| `?scenario=delete-error` | 履歴削除失敗 |
| `?scenario=no-appearance` | 見た目の条件なし |
| `?scenario=clarification` | 文章修正要求 |
| `?scenario=attributes` | 未確定の商品属性の選択 |

視覚仕様は [FRONTEND.md](../docs/FRONTEND.md#13-次期uiの視覚統一契約)、操作仕様は [SEARCH-FLOW.md](../SEARCH-FLOW.md)、実装・検証記録は [EXEC-157](../docs/GOAL.md#exec-157-オフラインモックを現行接続画面へ統一) を参照してください。

Noto Sans JPは `@fontsource-variable/noto-sans-jp` に含まれるSIL Open Font License 1.1の資材を使います。配布用の著作権表示とライセンス全文は [THIRD-PARTY-NOTICES.txt](public/THIRD-PARTY-NOTICES.txt) にまとめ、ビルド時もdistへ同梱します。起動後は `/THIRD-PARTY-NOTICES.txt` で確認できます。依存更新時は通知も更新してください。`public/images/` のSVGは本モック用に作成した合成キーボード画像です。Figmaの旧配色・装飾・画像をコピーしたものではありません。

`public/icons/wi-stars.svg` はFigma内の名前に対応するWeather Iconsの星素材です。取得元・変更内容・同梱ライセンスは [アイコン素材](public/icons/README.md) を参照してください。
