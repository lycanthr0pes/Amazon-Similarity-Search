import { useState } from "react";
import * as stylex from "@stylexjs/stylex";
import {
  Actions,
  Button,
  Dialog,
  ImageCard,
  ImageZoom,
  Note,
} from "./components";
import type { Conditions, Product } from "./model";
import { theme } from "./theme.stylex";
import { ProductName } from "./product-name";

export const fieldLabels: Record<keyof Conditions, string> = {
  product: "商品の種類",
  required: "必ずほしい",
  preferred: "できればほしい",
  excluded: "避けたい",
  budget: "予算",
};

export function ConditionSummary({
  conditions,
  input,
  useImages,
  variant = "plain",
  columns = 1,
}: {
  conditions: Conditions;
  input: string;
  useImages: boolean;
  variant?: "plain" | "cards";
  columns?: 1 | 2;
}) {
  return (
    <div {...stylex.props(layout.stack)}>
      <h3>確認した条件</h3>
      <p {...stylex.props(layout.small)}>固定のデモ条件（編集内容を反映）</p>
      <dl
        {...stylex.props(
          layout.definition,
          columns === 2 && layout.definitionColumns,
        )}
      >
        {Object.entries(conditions).map(([key, value]) => (
          <div key={key}>
            <dt {...stylex.props(layout.small)}>
              {fieldLabels[key as keyof Conditions]}
            </dt>
            <dd
              {...stylex.props(
                layout.definitionValue,
                variant === "cards" && layout.inputText,
              )}
            >
              {value || "指定なし"}
            </dd>
          </div>
        ))}
      </dl>
      <p>参考画像：{useImages ? "使用" : "なし"}</p>
      <details>
        <summary>入力した文章</summary>
        <p
          {...stylex.props(
            layout.wrap,
            variant === "cards" && layout.inputText,
          )}
        >
          {input}
        </p>
      </details>
    </div>
  );
}

export function ConditionEditor({
  conditions,
  onChange,
}: {
  conditions: Conditions;
  onChange: (value: Conditions) => void;
}) {
  return (
    <div {...stylex.props(layout.fields)}>
      {Object.entries(fieldLabels).map(([key, label]) => (
        <label key={key} {...stylex.props(layout.field)}>
          {label}
          <input
            {...stylex.props(layout.input)}
            value={conditions[key as keyof Conditions]}
            maxLength={500}
            inputMode={key === "budget" ? "numeric" : "text"}
            onChange={(event) =>
              onChange({ ...conditions, [key]: event.target.value })
            }
          />
        </label>
      ))}
    </div>
  );
}

export const MOCK_IMAGES = [
  {
    src: "/images/keyboard-white.svg",
    label: "参考画像",
    detail: "白・テンキーレス",
  },
  {
    src: "/images/keyboard-dark.svg",
    label: "比較用の偽画像：色",
    detail: "白から黒へ変更",
  },
  {
    src: "/images/keyboard-full.svg",
    label: "比較用の偽画像：形",
    detail: "テンキー付きへ変更",
  },
];

export function ImageGallery({ onOpen }: { onOpen: (index: number) => void }) {
  return (
    <div {...stylex.props(layout.stack)}>
      <div {...stylex.props(layout.imageRow)}>
        <ImageCard {...MOCK_IMAGES[0]} onOpen={() => onOpen(0)} />
        <div {...stylex.props(layout.stack)}>
          <h3>比較の基準になる1枚</h3>
          <p>了承した参考画像をそのまま使います。</p>
          <Note>
            すべて固定の合成画像です。実在する商品、仕様、在庫を表すものではありません。
          </Note>
        </div>
      </div>
      <h3>比較用の偽画像</h3>
      <p>見た目の条件を1つずつ変えた2枚です。</p>
      <div {...stylex.props(layout.imageRow)}>
        {MOCK_IMAGES.slice(1).map((item, i) => (
          <ImageCard key={item.src} {...item} onOpen={() => onOpen(i + 1)} />
        ))}
      </div>
    </div>
  );
}

const PRODUCT_CARD_PADDING = 25;
const CONDITION_NAMES: Record<string, string> = {
  静音性は未確認: "静音性",
  接続可能な機器は未確認: "接続可能な機器",
  テンキー付き: "テンキー",
  大きな本体: "本体サイズ",
};

function conditionNames(values: string[]) {
  return (
    values.map((value) => CONDITION_NAMES[value] ?? value).join("・") || "なし"
  );
}

export function Results({
  products,
  count,
  onCount,
  productUrl,
}: {
  products: Product[];
  count: number;
  onCount: (value: number) => void;
  productUrl?: (product: Product) => string | undefined;
}) {
  const [image, setImage] = useState<Product | null>(null);
  return (
    <div {...stylex.props(layout.stack)}>
      <div {...stylex.props(layout.resultToolbar)}>
        <p>{products.length}件の合成商品 · 条件に近い順（固定）</p>
        <label>
          表示件数{" "}
          <select
            aria-label="表示件数"
            value={count}
            onChange={(event) => onCount(Number(event.target.value))}
            {...stylex.props(layout.select)}
          >
            {Array.from({ length: 30 }, (_, i) => (
              <option key={i + 1} value={i + 1}>
                {i + 1}件
              </option>
            ))}
          </select>
        </label>
      </div>
      {products.length === 0 ? (
        <section {...stylex.props(layout.panel)}>
          <h2>条件に合う商品がありません</h2>
          <p>
            これは0件の結果を確認するためのモックです。条件を見直して新しく検索できます。
          </p>
        </section>
      ) : (
        <ul aria-label="検索結果" {...stylex.props(layout.resultGrid)}>
          {products.slice(0, count).map((item, index) => (
            <li key={item.id} {...stylex.props(layout.product)}>
              <div {...stylex.props(layout.resultToolbar)}>
                <span {...stylex.props(layout.rank)}>#{index + 1}</span>
                <span {...stylex.props(layout.small)}>合成商品</span>
              </div>
              <ImageZoom label={item.name} onOpen={() => setImage(item)}>
                <img
                  src={item.image}
                  alt={item.name}
                  width={304}
                  height={200}
                  {...stylex.props(layout.productImage)}
                />
              </ImageZoom>
              <ProductName name={item.name} url={productUrl?.(item)} />
              <p {...stylex.props(layout.price)}>
                ¥{item.price.toLocaleString("ja-JP")}
              </p>
              <p {...stylex.props(layout.small)}>
                評価 {item.rating.toFixed(1)} / 5 · {item.reviews}件（デモ）
              </p>
              <details {...stylex.props(layout.productEvidence)}>
                <summary {...stylex.props(layout.evidenceSummary)}>
                  検索条件
                </summary>
                <div {...stylex.props(layout.evidenceContent)}>
                  <p>一致：{item.matched.join("・") || "なし"}</p>
                  <p>未確認：{conditionNames(item.unknown)}</p>
                  <p>不一致：{conditionNames(item.mismatched)}</p>
                </div>
              </details>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        aria-label="トップに戻る"
        title="トップに戻る"
        onClick={() =>
          window.scrollTo({
            top: 0,
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
              .matches
              ? "instant"
              : "smooth",
          })
        }
        {...stylex.props(layout.backToTop)}
      >
        <svg
          aria-hidden="true"
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
        >
          <path
            d="M12 20V4m-7 7 7-7 7 7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {image && (
        <Dialog title={image.name} onClose={() => setImage(null)}>
          <img
            src={image.image}
            alt={image.name}
            {...stylex.props(layout.lightbox)}
          />
          <Note>固定の合成商品画像です。</Note>
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

export const layout = stylex.create({
  page: { width: 1120, marginInline: "auto", paddingBottom: 64 },
  header: {
    width: 1248,
    maxWidth: "calc(100% - 64px)",
    marginInline: "auto",
    marginTop: 24,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    paddingBlock: 19,
    paddingInline: 25,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerActions: { display: "flex", gap: 16, alignItems: "center" },
  brand: { display: "flex", gap: 16, alignItems: "center" },
  monogram: {
    width: 48,
    height: 48,
    padding: 1,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    display: "grid",
    placeItems: "center",
    fontWeight: 700,
  },
  brandName: { fontWeight: 700, letterSpacing: "-0.02em" },
  small: { fontSize: 14, lineHeight: "24px" },
  stack: { display: "flex", flexDirection: "column", gap: 24 },
  intro: {
    marginBottom: 32,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  eyebrow: { fontSize: 14, lineHeight: "24px", letterSpacing: "0.08em" },
  panel: {
    padding: 33,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
  },
  twoColumns: {
    display: "grid",
    gridTemplateColumns: "736px 352px",
    gap: 32,
    alignItems: "start",
  },
  heroColumns: { display: "grid", gridTemplateColumns: "1fr 288px", gap: 48 },
  field: { display: "flex", flexDirection: "column", gap: 12 },
  input: {
    outlineStyle: "none",
    width: "100%",
    padding: 17,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    backgroundColor: theme.note,
    color: theme.white,
    "::placeholder": { color: theme.white, opacity: 1 },
    fontSize: 16,
  },
  textarea: {
    backgroundColor: theme.note,
    outlineStyle: "none",
    minHeight: 168,
    resize: "vertical",
    marginTop: 16,
    "::placeholder": { color: "#a0a0a0" },
  },
  counter: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 14,
    lineHeight: "24px",
    marginTop: 8,
  },
  fields: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 },
  definition: { margin: 0, display: "flex", flexDirection: "column", gap: 16 },
  definitionColumns: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    columnGap: 32,
  },
  definitionValue: { margin: 0, overflowWrap: "anywhere" },
  wrap: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
  inputText: {
    backgroundColor: theme.note,
    borderRadius: theme.radius,
    padding: 16,
  },
  imageRow: { display: "flex", alignItems: "center", gap: 32 },
  footer: {
    borderTopWidth: 1,
    borderTopStyle: "solid",
    borderTopColor: theme.white,
    marginTop: 48,
    paddingTop: 24,
    fontSize: 14,
    lineHeight: "24px",
    display: "flex",
    justifyContent: "space-between",
  },
  resultToolbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
  },
  resultGrid: {
    listStyle: "none",
    padding: 0,
    margin: 0,
    display: "grid",
    gridTemplateColumns: "repeat(3, 352px)",
    gap: 32,
  },
  select: {
    outlineStyle: "none",
    marginLeft: 12,
    backgroundColor: theme.black,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    padding: 11,
    borderRadius: theme.radius,
  },
  product: {
    padding: PRODUCT_CARD_PADDING,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  rank: {
    position: "relative",
    top: -PRODUCT_CARD_PADDING,
    marginLeft: -PRODUCT_CARD_PADDING,
    minWidth: 80,
    paddingBlock: 5,
    paddingInline: 17,
    backgroundColor: theme.blue,
    color: theme.white,
    borderTopLeftRadius: theme.radius,
    borderTopRightRadius: 0,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: theme.radius,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    fontSize: 20,
    fontWeight: 600,
    lineHeight: "28px",
    textAlign: "center",
  },
  productImage: {
    width: "100%",
    height: 200,
    objectFit: "cover",
    borderRadius: theme.radius,
  },
  productEvidence: {
    fontSize: 14,
    lineHeight: "24px",
    padding: 16,
    backgroundColor: theme.note,
    borderRadius: theme.radius,
  },
  evidenceSummary: { cursor: "pointer" },
  evidenceContent: { marginTop: 12 },
  historyActions: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 24,
    marginTop: "auto",
  },
  historyGrid: {
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 16,
  },
  historyCard: { padding: 17, gap: 8, minWidth: 0 },
  price: { fontSize: 24, fontWeight: 600 },
  backToTop: {
    position: "fixed",
    right: 24,
    bottom: 32,
    zIndex: 2,
    width: 56,
    height: 56,
    padding: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.white,
    color: theme.black,
    borderWidth: 0,
    borderRadius: 100,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}, 0 0 20px 4px rgba(255, 255, 255, 0.35)`,
    cursor: "pointer",
  },
  lightbox: {
    width: "100%",
    height: 340,
    objectFit: "contain",
    marginBlock: 24,
  },
  historyPage: { paddingTop: 36 },
  error: {
    marginBottom: 24,
    padding: 21,
    backgroundColor: theme.note,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
  },
});
