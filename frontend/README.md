# Amazon Explorer UI

React + TypeScript + StyleXによるデスクトップ用オフラインモックです。任意の自然文入力、条件編集、任意の参考画像・比較画像確認、最終確認、5工程の商品調査、結果・検索履歴を操作できます。

表示する条件・商品12件・画像は固定の合成データです。入力を理解・検索せず、実バックエンド、Bonsai、外部API、認証情報を使いません。画像・Noto Sans JPもローカル配信します。編集した条件は確認画面へ反映しますが、固定の商品・比較結果は変えません。

Node.js 22.12以降を使用します。リポジトリルートからの初回準備と起動:

```sh
cd frontend
npm ci
npm run dev
```

開発画面は `http://127.0.0.1:5173/` です。依存取得は公開npmへの通信を行う環境準備です。準備後の画面利用はローカル配信だけで動作します。

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

`src/model.ts` が状態遷移と固定データ、`src/history.ts` がタブ内のsessionStorage、`src/components.tsx` と `src/screens.tsx` が共通表示部品、`src/App.tsx` がモックの応答時間と画面操作を担当します。StyleXは公式unpluginでCSSへ事前コンパイルし、`src/global.css` はフォント以外の共通resetだけを持ちます。表示部品は将来の通常検索でも利用する構成ですが、実サービスadapterとAPI接続は未実装です。

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

視覚仕様は [FRONTEND.md](../docs/FRONTEND.md#13-次期uiの視覚統一契約)、操作仕様は [SEARCH-FLOW.md](../SEARCH-FLOW.md)、実装・検証記録は [EXEC-117](../docs/GOAL.md#exec-117-react-stylexのオフライン画面) を参照してください。

Noto Sans JPは `@fontsource-variable/noto-sans-jp` に含まれるSIL Open Font License 1.1の資材を使います。依存パッケージのライセンスは各package内にあります。`public/images/` のSVGは本モック用に作成した合成キーボード画像です。Figmaの旧配色・装飾・画像をコピーしたものではありません。

`public/icons/wi-stars.svg` はFigma内の名前に対応するWeather Iconsの星素材です。取得元・変更内容・同梱ライセンスは [アイコン素材](public/icons/README.md) を参照してください。
