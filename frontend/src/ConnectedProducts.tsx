import * as stylex from "@stylexjs/stylex";
import { useState } from "react";
import { Actions, Button, Dialog, ImageZoom } from "./components";
import { BackToTop, ResultCount } from "./search-chrome";
import { layout } from "./screens";
import { ProductName } from "./product-name";
import { ConnectedScores } from "./ConnectedScores";
import type { SearchView } from "./connected-api";

export function ConnectedProducts({
  view,
  historical = false,
}: {
  view: SearchView;
  historical?: boolean;
}) {
  const [count, setCount] = useState(10);
  const [image, setImage] = useState<
    NonNullable<SearchView["products"]>[number] | null
  >(null);
  return (
    <div {...stylex.props(layout.stack)}>
      <div {...stylex.props(layout.resultToolbar)}>
        <p>{view.products?.length ?? 0}件の商品 · 条件に近い順</p>
        <ResultCount
          count={count}
          onCount={setCount}
          maximum={Math.max(30, view.products?.length ?? 0)}
        />
      </div>
      {view.products?.length === 0 && (
        <section {...stylex.props(layout.panel)}>
          <h2>条件に合う商品がありません</h2>
          <p>条件を見直して新しく検索できます。</p>
        </section>
      )}
      <ul aria-label="検索結果" {...stylex.props(layout.resultGrid)}>
        {view.products?.slice(0, count).map((product, index) => (
          <li key={index} {...stylex.props(layout.product, layout.resultCard)}>
            <div {...stylex.props(layout.productOverview)}>
              <div {...stylex.props(layout.resultToolbar)}>
                <span {...stylex.props(layout.rank)}>#{index + 1}</span>
              </div>
              {product.thumbnail ? (
                <ImageZoom
                  label={product.title}
                  onOpen={() => setImage(product)}
                >
                  <img
                    src={product.thumbnail}
                    alt={`${product.title}の商品画像`}
                    loading="lazy"
                    {...stylex.props(layout.productImage)}
                  />
                </ImageZoom>
              ) : (
                <p>
                  {historical && !view.historyContentAvailable
                    ? "商品画像は履歴に保存されていません"
                    : "商品画像は未取得"}
                </p>
              )}
              <ProductName
                name={product.title}
                url={product.url ?? undefined}
              />
              <p {...stylex.props(layout.price)}>
                {product.price === null
                  ? "価格は未確認"
                  : `¥${product.price.toLocaleString("ja-JP")}`}
              </p>
              {product.reviewRating !== undefined && (
                <p>
                  レビュースコア：
                  {product.reviewRating === null
                    ? "未取得"
                    : `${product.reviewRating.toFixed(1)} / 5`}
                </p>
              )}
            </div>
            {(product.scores || product.titleEnStatus) && (
              <details {...stylex.props(layout.productEvidence)}>
                <summary {...stylex.props(layout.evidenceSummary)}>
                  検索詳細
                </summary>
                <div {...stylex.props(layout.evidenceContent)}>
                  {product.titleEnStatus === "available" && (
                    <p>
                      英語タイトル：<span lang="en">{product.titleEn}</span>
                    </p>
                  )}
                  {product.titleEnStatus === "unavailable" && (
                    <p>英語タイトル未取得</p>
                  )}
                  {product.scores && (
                    <ConnectedScores
                      scores={product.scores}
                      labels={view.conditionLabels}
                      sortProfile={view.sortProfile}
                      imageMode={view.imageMode}
                    />
                  )}
                </div>
              </details>
            )}
          </li>
        ))}
      </ul>
      <BackToTop />
      {image?.thumbnail && (
        <Dialog title={image.title} onClose={() => setImage(null)}>
          <img
            src={image.thumbnail}
            alt={image.title}
            {...stylex.props(layout.lightbox)}
          />
          <Actions>
            <Button data-safe-focus onClick={() => setImage(null)}>
              閉じる
            </Button>
          </Actions>
        </Dialog>
      )}
    </div>
  );
}
