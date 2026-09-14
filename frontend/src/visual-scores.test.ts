import { expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
vi.mock("@stylexjs/stylex", () => ({
  create: (x: unknown) => x,
  props: () => ({}),
}));
import { ConnectedScores } from "./ConnectedScores";
import { parseSearchView } from "./connected-api";

it("shows independent visual scores in priority order for shared production and mock UI", () => {
  const scores = {
    title: { score_ja: 1, score_en: null, score: 1 },
    conditions: [],
    textImage: 0.8,
    image: 0.6,
    total: 0.8,
  };
  const html = renderToStaticMarkup(
    createElement(ConnectedScores, {
      scores,
      sortProfile: "excluded-title-conditions-text-image-review-v2",
    }),
  );
  expect(html).toContain("文章と画像：80.0");
  expect(html).toContain("画像同士：60.0");
  expect(html.indexOf("文章と画像")).toBeLessThan(html.indexOf("画像同士"));
  expect(html).not.toContain("参考合成点");
});

it("rejects invalid independent score values", () => {
  const view = {
    stage: "complete",
    revision: 1,
    products: [
      {
        title: "合成",
        price: 1,
        url: null,
        required: "一致",
        appearance: "補助",
        scores: {
          title: { score_ja: 1, score_en: null, score: 1 },
          conditions: [],
          image: 0.6,
          textImage: -0.1,
        },
      },
    ],
  };
  expect(() => parseSearchView(view)).toThrow();
});

it("rejects visual text evidence in image-free results", () => {
  const view = (textImage: number | null) => ({
    stage: "complete",
    revision: 1,
    imageMode: "off",
    images: [],
    products: [
      {
        title: "合成",
        price: 1,
        url: null,
        required: "一致",
        appearance: "未使用",
        scores: {
          title: { score_ja: 1, score_en: null, score: 1 },
          conditions: [],
          image: null,
          textImage,
        },
      },
    ],
  });
  expect(() => parseSearchView(view(null))).not.toThrow();
  expect(() => parseSearchView(view(0.4))).toThrow();
});
