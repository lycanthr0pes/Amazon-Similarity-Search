import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { SearchView } from "./connected-api";
import {
  conditionValues,
  conditionEditError,
  editedConditionSource,
  conditionsChanged,
} from "./condition-editor";

const fixture = JSON.parse(
  readFileSync(
    new URL("../../tests/fixtures/condition-group-edits.json", import.meta.url),
    "utf8",
  ),
);
const view: SearchView = fixture.view;

describe("grouped condition editing", () => {
  it("keeps missing categories empty and preserves original input without edits", () => {
    const draft = conditionValues(view);
    expect(draft).toEqual({
      required: "USB非対応, ブランド:合成",
      preferred: "",
      excluded: "電子レンジ対応",
      neutral: "取っ手",
    });
    expect(conditionsChanged(view, draft)).toBe(false);
    expect(editedConditionSource(view, view.productName!, draft)).toBe(
      view.input,
    );
    expect(editedConditionSource(view, "タンブラー", draft)).toBe(
      "タンブラー。" + view.conditionText,
    );
  });
  it("preserves negative attribute values, neutral quotes and metadata while adding wishes", () => {
    const draft = { ...conditionValues(view), ...fixture.edits };
    expect(conditionEditError(view, draft)).toBeNull();
    expect(editedConditionSource(view, view.productName!, draft)).toBe(
      fixture.expectedSource,
    );
  });
  it("removes cleared conditions and adds neutral targets without negative scoring", () => {
    const draft = {
      required: "",
      preferred: "軽い, 白",
      excluded: "",
      neutral: "色",
    };
    expect(editedConditionSource(view, view.productName!, draft)).toBe(
      "マグカップ。できれば軽い。できれば白。色にはこだわらない。",
    );
  });
  it("does not split numbers silently or let sentence separators change a group's scope", () => {
    const draft = conditionValues(view);
    expect(
      conditionEditError(view, { ...draft, preferred: "3,000円以下" }),
    ).toContain("桁区切り");
    expect(
      conditionEditError(view, { ...draft, preferred: "赤。白" }),
    ).toContain("半角カンマ");
    expect(
      conditionEditError(view, { ...draft, preferred: "赤, 白" }),
    ).toBeNull();
    expect(
      conditionEditError(view, {
        ...draft,
        preferred: Array(25).fill("赤").join(", "),
      }),
    ).toContain("24個");
  });
});

it("asks for bare targets when new modifiers would override the chosen category", () => {
  const draft = conditionValues(view);
  expect(
    conditionEditError(view, { ...draft, preferred: "赤は避けたい" }),
  ).toContain("特徴だけ");
  expect(
    conditionEditError(view, { ...draft, required: "できれば白" }),
  ).toContain("特徴だけ");
  expect(
    conditionEditError(view, {
      ...draft,
      required: "USB非対応, ノンカフェイン",
    }),
  ).toBeNull();
});
