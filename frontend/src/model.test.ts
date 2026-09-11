import { describe, expect, it } from "vitest";
import {
  DEFAULT_CONDITIONS,
  PRODUCTS,
  initialState,
  isBusy,
  reducer,
  type Action,
  type State,
} from "./model";

const NOW = 1_800_000_000_000;

function apply(state: State, ...actions: Action[]): State {
  return actions.reduce(reducer, state);
}

function review(): State {
  return apply(
    initialState,
    { type: "INPUT", value: "  静かな作業道具を探したい（合成テスト入力）  " },
    { type: "ORGANIZE" },
    { type: "ORGANIZED" },
  );
}

function reference(): State {
  return apply(
    review(),
    { type: "IMAGES", value: true },
    { type: "START_REFERENCE", now: NOW },
    { type: "REFERENCE_READY", now: NOW + 1_000 },
  );
}

function comparison(): State {
  return apply(
    reference(),
    { type: "APPROVE_REFERENCE", now: NOW + 2_000 },
    { type: "COMPARISONS_READY" },
  );
}

describe("offline search workflow", () => {
  it("rejects blank and overlong input before starting work", () => {
    expect(reducer(initialState, { type: "ORGANIZE" })).toMatchObject({
      screen: "input",
      error: expect.any(String),
    });
    const overlong = apply(
      initialState,
      { type: "INPUT", value: "あ".repeat(2_001) },
      { type: "ORGANIZE" },
    );
    expect(overlong.screen).toBe("input");
    expect(overlong.error).not.toBeNull();
  });

  it("keeps arbitrary input verbatim and supplies fixed demo conditions", () => {
    const state = review();
    expect(state.input).toBe("  静かな作業道具を探したい（合成テスト入力）  ");
    expect(state.conditions).toEqual(DEFAULT_CONDITIONS);
    expect(state.useImages).toBe(false);
    expect(state.screen).toBe("review");
  });

  it("keeps the image option selected on the input page through condition review", () => {
    const selected = reducer(initialState, { type: "IMAGES", value: true });
    expect(selected.useImages).toBe(true);
    const state = apply(
      selected,
      { type: "INPUT", value: "白いキーボード（合成入力）" },
      { type: "ORGANIZE" },
      { type: "ORGANIZED" },
    );
    expect(state).toMatchObject({ screen: "review", useImages: true });
    expect(reducer(state, { type: "IMAGES", value: false }).useImages).toBe(
      false,
    );
  });

  it("requires result confirmation after all five research stages", () => {
    let state = apply(
      review(),
      { type: "FINALIZE", now: NOW },
      { type: "SEARCH", now: NOW },
    );
    expect(state.screen).toBe("research");
    expect(reducer(state, { type: "SEARCH", now: NOW })).toBe(state);
    expect(reducer(state, { type: "SHOW_RESULTS" })).toBe(state);
    for (let step = 0; step < 4; step += 1) {
      state = reducer(state, { type: "TICK" });
      expect(state.screen).toBe("research");
    }
    state = reducer(state, { type: "TICK" });
    expect(state).toMatchObject({ screen: "complete", researchStep: 5 });
    expect(reducer(state, { type: "TICK" })).toBe(state);
    expect(reducer(state, { type: "SHOW_RESULTS" }).screen).toBe("results");
  });

  it("blocks progression until edited conditions are explicitly applied", () => {
    let state = reducer(review(), {
      type: "EDIT_CONDITIONS",
      value: { ...DEFAULT_CONDITIONS, preferred: "日本語配列" },
    });
    expect(state.conditionsDirty).toBe(true);
    expect(reducer(state, { type: "FINALIZE", now: NOW })).toBe(state);
    expect(reducer(state, { type: "WITHOUT_IMAGES", now: NOW })).toBe(state);
    state = reducer(state, { type: "IMAGES", value: true });
    expect(reducer(state, { type: "START_REFERENCE", now: NOW })).toBe(state);
    state = reducer(state, { type: "APPLY_CONDITIONS" });
    expect(state.conditionsDirty).toBe(false);
    expect(state.conditions.preferred).toBe("日本語配列");
    expect(reducer(state, { type: "START_REFERENCE", now: NOW }).screen).toBe(
      "referenceGenerating",
    );
  });

  it("does not create a dirty draft when conditions are unchanged", () => {
    const state = review();
    expect(
      reducer(state, {
        type: "EDIT_CONDITIONS",
        value: { ...state.conditions },
      }),
    ).toBe(state);
  });

  it("requires a nonempty product before accepting edited conditions", () => {
    const state = apply(
      review(),
      {
        type: "EDIT_CONDITIONS",
        value: { ...DEFAULT_CONDITIONS, product: " " },
      },
      { type: "APPLY_CONDITIONS" },
    );
    expect(state.conditionsDirty).toBe(true);
    expect(state.error).not.toBeNull();
  });

  it("stops after the reference image and requires an explicit approval", () => {
    const state = reference();
    expect(state).toMatchObject({ screen: "referenceReview", attempts: 1 });
    expect(reducer(state, { type: "COMPARISONS_READY" })).toBe(state);
    expect(reducer(state, { type: "FINALIZE", now: NOW })).toBe(state);
    const approved = reducer(state, {
      type: "APPROVE_REFERENCE",
      now: NOW + 2_000,
    });
    expect(approved.screen).toBe("comparisonGenerating");
    expect(
      reducer(approved, { type: "APPROVE_REFERENCE", now: NOW + 2_000 }),
    ).toBe(approved);
    const ready = reducer(approved, { type: "COMPARISONS_READY" });
    expect(
      reducer(ready, { type: "APPROVE_REFERENCE", now: NOW + 2_000 }),
    ).toBe(ready);
    expect(reducer(ready, { type: "FINALIZE", now: NOW + 3_000 }).screen).toBe(
      "final",
    );
  });

  it("expires the reference approval at fifteen minutes", () => {
    const state = reference();
    const expired = reducer(state, {
      type: "APPROVE_REFERENCE",
      now: NOW + 1_000 + 15 * 60_000,
    });
    expect(expired.screen).toBe("referenceReview");
    expect(expired.error).not.toBeNull();
    expect(reducer(expired, { type: "WITHOUT_IMAGES", now: NOW }).screen).toBe(
      "final",
    );
  });

  it("limits generation attempts across backward navigation and edits", () => {
    let state = reducer(comparison(), { type: "REGENERATE", now: NOW + 3_000 });
    expect(state).toMatchObject({
      screen: "referenceGenerating",
      attempts: 2,
      referenceExpiresAt: null,
    });
    state = apply(
      state,
      { type: "REFERENCE_READY", now: NOW + 4_000 },
      { type: "BACK" },
    );
    expect(state).toMatchObject({
      screen: "review",
      attempts: 2,
      referenceExpiresAt: null,
    });
    expect(reducer(state, { type: "START_REFERENCE", now: NOW }).screen).toBe(
      "review",
    );
    state = apply(
      state,
      { type: "BACK" },
      { type: "INPUT", value: "別の合成入力" },
      { type: "ORGANIZE" },
      { type: "ORGANIZED" },
    );
    expect(state.attempts).toBe(2);
    expect(reducer(state, { type: "RESET" }).attempts).toBe(0);
  });

  it("invalidates image confirmations when returning to condition review", () => {
    const state = apply(
      comparison(),
      { type: "FINALIZE", now: NOW },
      { type: "BACK" },
    );
    expect(state).toMatchObject({
      screen: "review",
      referenceExpiresAt: null,
      finalExpiresAt: null,
    });
    expect(reducer(state, { type: "FINALIZE", now: NOW })).toBe(state);
    expect(reducer(state, { type: "APPROVE_REFERENCE", now: NOW })).toBe(state);
  });

  it("allows skipping images without carrying an old image approval", () => {
    const state = reducer(comparison(), { type: "WITHOUT_IMAGES", now: NOW });
    expect(state).toMatchObject({
      screen: "final",
      useImages: false,
      referenceExpiresAt: null,
    });
    expect(reducer(state, { type: "SEARCH", now: NOW }).screen).toBe(
      "research",
    );
  });

  it("blocks expired final confirmation until it is explicitly refreshed", () => {
    let state = reducer(review(), { type: "FINALIZE", now: NOW });
    const expiredAt = NOW + 15 * 60_000;
    state = reducer(state, { type: "SEARCH", now: expiredAt });
    expect(state.screen).toBe("final");
    expect(state.error).not.toBeNull();
    state = reducer(state, { type: "FINALIZE", now: expiredAt });
    expect(state.screen).toBe("final");
    expect(state.error).toBeNull();
    expect(reducer(state, { type: "SEARCH", now: expiredAt }).screen).toBe(
      "research",
    );
  });

  it("rejects late completion callbacks after cancellation and restart", () => {
    let state = apply(
      review(),
      { type: "FINALIZE", now: NOW },
      { type: "SEARCH", now: NOW },
    );
    const staleRevision = state.revision;
    state = apply(state, { type: "CANCEL" }, { type: "SEARCH", now: NOW });
    expect(state.revision).not.toBe(staleRevision);
    expect(reducer(state, { type: "TICK", revision: staleRevision })).toBe(
      state,
    );
    expect(
      reducer(state, { type: "TICK", revision: state.revision }).researchStep,
    ).toBe(1);
  });

  it("ignores edits, navigation, and duplicate starts while work is running", () => {
    const state = apply(
      initialState,
      { type: "INPUT", value: "合成入力" },
      { type: "ORGANIZE" },
    );
    expect(isBusy(state)).toBe(true);
    for (const action of [
      { type: "INPUT", value: "置換" },
      { type: "EDIT_CONDITIONS", value: DEFAULT_CONDITIONS },
      { type: "ORGANIZE" },
      { type: "IMAGES", value: true },
      { type: "BACK" },
      { type: "WITHOUT_IMAGES", now: NOW },
    ] satisfies Action[]) {
      expect(reducer(state, action)).toBe(state);
    }
  });

  it.each([
    "organizing",
    "referenceGenerating",
    "comparisonGenerating",
    "research",
  ] as const)(
    "new search resets %s and rejects its late completion",
    (screen) => {
      const previous: State = {
        ...initialState,
        screen,
        input: "合成入力",
        revision: 7,
      };
      const reset = reducer(previous, { type: "RESET" });
      expect(reset).toMatchObject({ screen: "input", input: "", revision: 8 });
      expect(
        reducer(reset, {
          type: "FAIL",
          revision: 7,
          message: "遅延した旧処理",
        }),
      ).toBe(reset);
      expect(reducer(reset, { type: "TICK", revision: 7 })).toBe(reset);
    },
  );

  it("cannot adopt failed comparison images or reuse the same approval", () => {
    const state = apply(
      reference(),
      { type: "APPROVE_REFERENCE", now: NOW },
      { type: "FAIL", message: "比較画像を表示できませんでした" },
    );
    expect(state).toMatchObject({
      screen: "comparisonReview",
      error: "比較画像を表示できませんでした",
    });
    expect(reducer(state, { type: "FINALIZE", now: NOW })).toBe(state);
    expect(reducer(state, { type: "APPROVE_REFERENCE", now: NOW })).toBe(state);
    expect(reducer(state, { type: "REGENERATE", now: NOW }).screen).toBe(
      "referenceGenerating",
    );
  });

  it("keeps failed work recoverable without completing or automatically retrying", () => {
    const failedReference = apply(
      review(),
      { type: "IMAGES", value: true },
      { type: "START_REFERENCE", now: NOW },
      { type: "FAIL", message: "参考画像を表示できませんでした" },
    );
    expect(failedReference).toMatchObject({
      screen: "referenceReview",
      referenceExpiresAt: null,
      attempts: 1,
    });
    expect(
      reducer(failedReference, { type: "APPROVE_REFERENCE", now: NOW }).screen,
    ).toBe("referenceReview");
    const research = apply(
      review(),
      { type: "FINALIZE", now: NOW },
      { type: "SEARCH", now: NOW },
    );
    const failedResearch = reducer(research, {
      type: "FAIL",
      message: "商品調査を表示できませんでした",
    });
    expect(failedResearch).toMatchObject({ screen: "final", researchStep: 0 });
    expect(isBusy(failedResearch)).toBe(false);
    expect(reducer(failedResearch, { type: "TICK" })).toBe(failedResearch);
    expect(reducer(failedResearch, { type: "SEARCH", now: NOW }).screen).toBe(
      "research",
    );
  });

  it("rejects out-of-order callbacks and invalid clocks", () => {
    for (const action of [
      { type: "ORGANIZED" },
      { type: "REFERENCE_READY", now: NOW },
      { type: "COMPARISONS_READY" },
      { type: "SEARCH", now: NOW },
      { type: "SHOW_RESULTS" },
      { type: "TICK" },
    ] satisfies Action[]) {
      expect(reducer(initialState, action)).toBe(initialState);
    }
    const state = reducer(review(), { type: "IMAGES", value: true });
    expect(reducer(state, { type: "START_REFERENCE", now: Number.NaN })).toBe(
      state,
    );
    expect(
      reducer(review(), { type: "FINALIZE", now: Number.POSITIVE_INFINITY }),
    ).toEqual(review());
  });

  it("provides a stable collection of synthetic products with local images", () => {
    expect(PRODUCTS.length).toBeGreaterThanOrEqual(12);
    expect(new Set(PRODUCTS.map((product) => product.id)).size).toBe(
      PRODUCTS.length,
    );
    expect(
      PRODUCTS.every((product) => product.image.startsWith("/images/")),
    ).toBe(true);
    expect(
      PRODUCTS.every(
        (product) =>
          product.price > 0 && product.rating >= 0 && product.rating <= 5,
      ),
    ).toBe(true);
    expect(PRODUCTS.some((product) => product.unknown.length > 0)).toBe(true);
  });

  it("keeps an explicit full-size mismatch after the fixed compatible and uncertain examples", () => {
    const wide = PRODUCTS.find(
      (product) => product.name === "Wide Keys 104 フルサイズ",
    );
    expect(wide?.mismatched).toEqual(["テンキー付き", "大きな本体"]);
    expect(PRODUCTS.every((product) => Array.isArray(product.mismatched))).toBe(
      true,
    );
    expect(PRODUCTS.at(-1)).toBe(wide);
    expect(
      PRODUCTS.slice(0, -1).every((product) => product.mismatched.length === 0),
    ).toBe(true);
    expect(wide?.matched).not.toContain("コンパクト");
  });
});
