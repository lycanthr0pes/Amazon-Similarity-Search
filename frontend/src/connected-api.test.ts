import { describe, expect, it } from "vitest";
import { parseSearchView } from "./connected-api";

describe("connected search responses", () => {
  it("validates thumbnail sources and the displayed bilingual maxima", () => {
    const product = {
      title: "合成の商品",
      price: 1000,
      url: null,
      required: "一致",
      appearance: "外観評価",
      thumbnail: "data:image/png;base64,AA==",
      scores: {
        title: { score_ja: 0.2, score_en: 0.8, score: 0.8 },
        image: 0.6,
        total: 0.7,
        conditions: [],
      },
    };
    const view = (extra: object) => ({
      stage: "complete",
      revision: 5,
      products: [{ ...product, ...extra }],
    });
    expect(parseSearchView(view({})).products).toHaveLength(1);
    for (const extra of [
      { thumbnail: "https://example.com/tracker.png" },
      { thumbnail: "data:image/svg+xml;base64,AA==" },
      { scores: { ...product.scores, image: Number.NaN } },
      {
        scores: {
          ...product.scores,
          title: { score_ja: 0.2, score_en: 0.8, score: 0.2 },
        },
      },
      {
        scores: {
          ...product.scores,
          conditions: [
            {
              requirement_id: "condition-1",
              strength: "excluded",
              score_ja: 0.8,
              score_en: 0.2,
              score: 0.2,
            },
          ],
        },
      },
    ]) {
      expect(() => parseSearchView(view(extra))).toThrow();
    }
  });
  it("distinguishes bilingual, missing and legacy titles and rejects inconsistent pairs", () => {
    const product = {
      title: "合成マグ",
      price: 2000,
      url: null,
      required: "一致",
      appearance: "外観は未確認",
    };
    for (const extra of [
      {},
      { titleEn: "Synthetic Mug", titleEnStatus: "available" },
      { titleEn: null, titleEnStatus: "unavailable" },
    ]) {
      expect(
        parseSearchView({
          stage: "complete",
          revision: 5,
          products: [{ ...product, ...extra }],
        }).products,
      ).toHaveLength(1);
    }
    for (const extra of [
      { titleEn: "unbound" },
      { titleEn: null, titleEnStatus: "available" },
      { titleEn: "", titleEnStatus: "available" },
      { titleEn: "invented", titleEnStatus: "unavailable" },
    ]) {
      expect(() =>
        parseSearchView({
          stage: "complete",
          revision: 5,
          products: [{ ...product, ...extra }],
        }),
      ).toThrow();
    }
  });
  it("rejects completed or confirmation states with missing required content", () => {
    for (const stage of [
      "complete",
      "query",
      "reference",
      "comparison",
      "final",
    ]) {
      expect(() => parseSearchView({ stage, revision: 1 })).toThrow();
    }
  });
  it("rejects unknown stages and malformed products", () => {
    expect(() => parseSearchView({ stage: "invented", revision: 0 })).toThrow();
    expect(() =>
      parseSearchView({ stage: "complete", revision: 1, products: [{}] }),
    ).toThrow();
  });

  it("accepts a server-owned confirmation without starting a request", () => {
    expect(
      parseSearchView({
        stage: "reference",
        revision: 2,
        images: ["data:image/png;base64,AA=="],
      }).stage,
    ).toBe("reference");
  });

  it("rejects remote preview images and unsafe product links", () => {
    expect(() =>
      parseSearchView({
        stage: "reference",
        revision: 2,
        images: ["https://example.com/image.png"],
      }),
    ).toThrow();
    expect(() =>
      parseSearchView({
        stage: "complete",
        revision: 5,
        products: [
          {
            title: "example",
            price: 10,
            url: "javascript:alert(1)",
            required: "一致",
            appearance: "外観は未確認",
          },
        ],
      }),
    ).toThrow();
  });
});

it("rejects invalid review ratings and unknown ranking profiles", () => {
  const view = {
    stage: "complete",
    revision: 1,
    products: [
      {
        title: "合成商品",
        price: 1000,
        url: null,
        required: "一致",
        appearance: "外観は未確認",
        reviewRating: 4.5,
      },
    ],
  };
  expect(parseSearchView(view).products).toHaveLength(1);
  for (const rating of [-1, 6, Number.NaN, "4.5"]) {
    expect(() =>
      parseSearchView({
        ...view,
        products: [{ ...view.products[0], reviewRating: rating }],
      }),
    ).toThrow();
  }
  expect(() => parseSearchView({ ...view, sortProfile: "unknown" })).toThrow();
});

it("validates source-bound condition classifications and correction issues", () => {
  const row = {
    start: 4,
    end: 10,
    quote: "赤でも構わない",
    target: "赤",
    strength: "neutral",
    reason: "permission",
  };
  const view = {
    stage: "clarification",
    revision: 1,
    conditionReview: [row],
    conditionIssues: [
      {
        start: 4,
        end: 10,
        quote: "赤が不要ではない",
        code: "ambiguous_negation",
      },
    ],
  };
  expect(parseSearchView(view).conditionReview?.[0].strength).toBe("neutral");
  for (const change of [
    { strength: "invented" },
    { start: -1 },
    { end: 2001 },
    { reason: "invented" },
    { target: "" },
  ]) {
    expect(() =>
      parseSearchView({ ...view, conditionReview: [{ ...row, ...change }] }),
    ).toThrow();
  }
  expect(() =>
    parseSearchView({
      ...view,
      conditionIssues: [{ ...view.conditionIssues[0], code: "raw_exception" }],
    }),
  ).toThrow();
});

it("accepts image-free confirmation and rejects mixed image evidence", () => {
  const value = { stage: "final", revision: 2, imageMode: "off", images: [] };
  expect(parseSearchView(value).imageMode).toBe("off");
  expect(() => parseSearchView({ ...value, imageMode: "on" })).toThrow();
  expect(() => parseSearchView({ ...value, stage: "reference" })).toThrow();
  expect(() => parseSearchView({ ...value, imageMode: undefined })).toThrow();
  expect(() => parseSearchView({ ...value, canSkipImages: "true" })).toThrow();
});

it("validates server-owned progress and action capabilities", () => {
  const state = {
    stage: "working",
    revision: 2,
    workingAction: "search",
    researchStep: 0,
    canCancel: true,
    referenceRemaining: 1,
  };
  expect(parseSearchView(state).canCancel).toBe(true);
  for (const change of [
    { referenceRemaining: 3 },
    { researchStep: 6 },
    { researchStep: -1 },
    { canCancel: "true" },
    { canReset: 1 },
    { workingAction: "unknown" },
  ]) {
    expect(() => parseSearchView({ ...state, ...change })).toThrow();
  }
});

it("accepts bounded direct-edit fields and preserves older responses", () => {
  const base = { stage: "query", revision: 1, queries: ["マグカップ"] };
  expect(parseSearchView(base).productName).toBeUndefined();
  expect(
    parseSearchView({ ...base, productName: "マグカップ", conditionText: "" })
      .conditionText,
  ).toBe("");
  for (const fields of [
    { productName: "" },
    { productName: 12 },
    { productName: "あ".repeat(101) },
    { conditionText: [] },
    { conditionText: "あ".repeat(2001) },
  ]) {
    expect(() => parseSearchView({ ...base, ...fields })).toThrow(
      "Invalid editable terms",
    );
  }
});

it("keeps prepared older sessions editable without restarting or reinterpreting inline phrases", () => {
  const base = {
    stage: "query",
    revision: 2,
    input: "マグカップ。できれば赤。",
    queries: ["マグカップ"],
    conditionReview: [
      {
        start: 6,
        end: 11,
        quote: "できれば赤",
        target: "赤",
        strength: "preferred",
        reason: "preference_prefix",
      },
    ],
  };
  expect(parseSearchView(base)).toMatchObject({
    productName: "マグカップ",
    conditionText: "できれば赤。",
  });
  expect(
    parseSearchView({
      ...base,
      input: "赤いマグカップを探しています。",
      conditionReview: [],
    }).productName,
  ).toBeUndefined();
});

it("allows display thumbnails in image-free results but still rejects image scores", () => {
  const product = {
    title: "合成商品",
    price: 1000,
    url: null,
    required: "一致",
    appearance: "画像評価なし",
    thumbnail: "data:image/png;base64,AA==",
    scores: {
      title: { score_ja: 1, score_en: null, score: 1 },
      image: null,
      conditions: [],
    },
  };
  const view = {
    stage: "complete",
    revision: 1,
    imageMode: "off",
    images: [],
    products: [product],
  };
  expect(parseSearchView(view).products?.[0].thumbnail).toBe(product.thumbnail);
  expect(() =>
    parseSearchView({
      ...view,
      products: [{ ...product, scores: { ...product.scores, image: 0.8 } }],
    }),
  ).toThrow();
});
