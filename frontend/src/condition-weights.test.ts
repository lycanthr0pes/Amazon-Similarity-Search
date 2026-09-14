import { expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
vi.mock("@stylexjs/stylex", () => ({
  create: (x: unknown) => x,
  props: () => ({}),
}));
import { ConnectedScores } from "./ConnectedScores";

it("shows aggregation weights separately from bilingual match scores", () => {
  const html = renderToStaticMarkup(
    createElement(ConnectedScores, {
      scores: {
        title: { score_ja: 1, score_en: null, score: 1 },
        conditions: [
          {
            requirement_id: "first",
            strength: "required",
            score_ja: 0.6,
            score_en: 0.8,
            score: 0.8,
            weight: 2,
          },
        ],
      },
      labels: { first: "電子レンジ対応" },
    }),
  );
  expect(html).toContain("重み");
  expect(html).toContain("2倍");
  expect(html).toContain("80.0");
});

it("does not invent weights for saved legacy scores", () => {
  const html = renderToStaticMarkup(
    createElement(ConnectedScores, {
      scores: {
        title: { score_ja: 1, score_en: null, score: 1 },
        conditions: [
          {
            requirement_id: "old",
            strength: "required",
            score_ja: 0.6,
            score_en: null,
            score: 0.6,
          },
        ],
      },
    }),
  );
  expect(html).not.toContain("重み");
  expect(html).not.toContain("倍");
});
