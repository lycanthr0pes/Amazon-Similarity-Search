import type { SearchView } from "./connected-api";

export const conditionLabels = {
  required: "優先条件",
  preferred: "希望条件",
  excluded: "否定条件",
  neutral: "指定なし",
};
export type ConditionStrength = keyof typeof conditionLabels;
export type ConditionDraft = Record<ConditionStrength, string>;
export const conditionStrengths = Object.keys(
  conditionLabels,
) as ConditionStrength[];
type Entry = { strength: ConditionStrength; target: string; quote: string };

function entries(view: SearchView): Entry[] {
  const rows: Entry[] = [...(view.conditionReview ?? [])];
  let remaining = view.conditionText ?? "";
  for (const row of rows) remaining = remaining.replace(row.quote, "");
  // Brand/model clauses may be in the editable source without scoring rows.
  for (const quote of remaining
    .split(/[。\n]/)
    .map((v) => v.trim())
    .filter(Boolean)) {
    rows.push({ strength: "required", target: quote, quote });
  }
  return rows;
}

export function conditionValues(view: SearchView): ConditionDraft {
  const rows = entries(view);
  return Object.fromEntries(
    conditionStrengths.map((strength) => [
      strength,
      rows
        .filter((r) => r.strength === strength)
        .map((r) => r.target)
        .join(", "),
    ]),
  ) as ConditionDraft;
}

export function conditionsChanged(
  view: SearchView,
  draft: ConditionDraft,
): boolean {
  const original = conditionValues(view);
  return conditionStrengths.some((key) => draft[key] !== original[key]);
}

function items(value: string): string[] {
  return value
    .split(/[,，、\n]/)
    .map((v) => v.trim())
    .filter(Boolean);
}

export function conditionEditError(
  view: SearchView,
  draft: ConditionDraft,
): string | null {
  const original = conditionValues(view);
  for (const key of conditionStrengths) {
    if (draft[key] === original[key]) continue;
    if (/\d,\d{3}(?:\D|$)/.test(draft[key]))
      return "金額などの数字には桁区切りのカンマを使わず、3000円以下のように入力してください。";
    if (items(draft[key]).some((item) => /[。\r]/.test(item)))
      return "複数の条件は句点ではなく、半角カンマ（,）で区切ってください。";
    const known = entries(view)
      .filter((row) => row.strength === key)
      .map((row) => row.target);
    const modifier =
      /^(?:できれば|出来れば|なるべく|可能なら|できるだけ|出来るだけ|必ず|絶対に)|(?:避けたい|避けます|避けてほしい|除外|不要|いらない|要らない|いりません|必要ない|必要ありません|なし|無し|以外|ではない|こだわらない|こだわりません|構わない|構いません|なくてもよい|なくてもいい|希望|希望します|必須|必要|だとうれしい|あるとよい)(?:です)?$/;
    if (
      items(draft[key]).some(
        (item) => !known.includes(item) && modifier.test(item),
      )
    )
      return "希望・否定などの表現は付けず、特徴だけを対応する条件欄に入力してください。";
  }
  if (
    conditionStrengths.reduce(
      (count, key) => count + items(draft[key]).length,
      0,
    ) > 24
  )
    return "条件は24個以内で入力してください。";
  return null;
}

function modifiedPhrase(strength: ConditionStrength, target: string): string {
  switch (strength) {
    case "preferred":
      return `できれば${target}`;
    case "excluded":
      return `${target}は避けたい`;
    case "neutral":
      return `${target}にはこだわらない`;
    case "required":
      return target;
  }
}

export function editedConditionSource(
  view: SearchView,
  product: string,
  draft: ConditionDraft,
): string {
  if (!conditionsChanged(view, draft)) {
    if (product === view.productName) return view.input ?? "";
    return `${product.trim()}。${view.conditionText ?? ""}`;
  }
  const original = conditionValues(view);
  const rows = entries(view);
  const clauses = conditionStrengths.flatMap((strength) => {
    const originals = rows.filter((row) => row.strength === strength);
    if (draft[strength] === original[strength])
      return originals.map((row) => row.quote);
    return items(draft[strength]).map(
      (target) =>
        originals.find((row) => row.target === target)?.quote ??
        modifiedPhrase(strength, target),
    );
  });
  return [product.trim(), ...clauses].join("。") + "。";
}
