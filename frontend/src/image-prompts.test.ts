import { describe, expect, it } from "vitest";
import { validPrompts } from "./image-prompt-values";
import { parseSearchView } from "./connected-api";

describe("image prompt editing", () => {
  it("checks each prompt before submission", () => {
    expect(
      validPrompts({
        reference: "A reference.",
        comparison: { a: "A comparison." },
      }),
    ).toBe(true);
    for (const value of [
      "",
      " ",
      "x".repeat(12001),
      "あ".repeat(11000),
      "https://example.com",
      "bad\u0000text",
    ]) {
      expect(
        validPrompts({ reference: "A reference.", comparison: { a: value } }),
      ).toBe(false);
    }
  });
  it("validates server prompt maps and the comparison generation operation", () => {
    const view = {
      stage: "working",
      revision: 1,
      workingAction: "regenerate_comparisons",
      imagePrompts: {
        reference: "Reference.",
        comparison: { a: "Comparison." },
      },
      canRegenerateComparisons: true,
    };
    expect(parseSearchView(view).imagePrompts).toEqual(view.imagePrompts);
    expect(() =>
      parseSearchView({
        ...view,
        imagePrompts: { reference: "Reference.", comparison: [] },
      }),
    ).toThrow();
  });
});
