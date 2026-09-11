import { describe, expect, it } from "vitest";
import {
  deleteHistory,
  HISTORY_KEY,
  HistoryError,
  readHistory,
  saveHistory,
  type HistoryEntry,
  type HistoryStorage,
} from "./history";

const NOW = 1_800_000_000_000;
const DAY = 24 * 60 * 60 * 1_000;

class MemoryStorage implements HistoryStorage {
  value: string | null = null;
  failRead = false;
  failWrite = false;

  getItem(key: string): string | null {
    expect(key).toBe(HISTORY_KEY);
    if (this.failRead) {
      throw new Error("private storage failure");
    }
    return this.value;
  }

  setItem(key: string, value: string): void {
    expect(key).toBe(HISTORY_KEY);
    if (this.failWrite) {
      throw new Error("private quota details");
    }
    this.value = value;
  }
}

function entry(id = "mock-run-1", createdAt = NOW): HistoryEntry {
  return {
    id,
    createdAt,
    input: "表示確認用の合成入力",
    conditions: {
      product: "キーボード",
      required: "日本語配列",
      preferred: "白色",
      excluded: "テンキー付き",
      budget: "15,000円以内",
    },
    useImages: false,
    products: [
      {
        id: "mock-keyboard-01",
        name: "合成キーボード",
        price: 8_000,
        rating: 4.2,
        reviews: 100,
        image: "/images/keyboard-white.svg",
        matched: ["日本語配列"],
        unknown: ["静音性は確認できません"],
        mismatched: [],
      },
    ],
  };
}

describe("local mock history", () => {
  it("returns an empty list only when no history has been saved", () => {
    expect(readHistory(new MemoryStorage(), NOW)).toEqual([]);
  });

  it("saves a completed zero-result run once and retains its first snapshot", () => {
    const storage = new MemoryStorage();
    const empty = { ...entry(), products: [] };
    saveHistory(storage, empty, NOW);
    const duplicate = { ...entry(), input: "後から変更した合成入力" };

    expect(saveHistory(storage, duplicate, NOW)).toEqual([empty]);
    expect(readHistory(storage, NOW)).toEqual([empty]);
  });

  it("detaches stored and returned conditions and product arrays", () => {
    const storage = new MemoryStorage();
    const original = entry();
    const saved = saveHistory(storage, original, NOW);
    original.conditions.required = "変更された条件";
    original.products[0].matched.push("変更された説明");
    saved[0].conditions.product = "変更された種類";
    saved[0].products.splice(0);

    expect(readHistory(storage, NOW)).toEqual([entry()]);
  });

  it("keeps at most 30 newest complete snapshots", () => {
    const storage = new MemoryStorage();
    for (let index = 0; index < 32; index += 1) {
      saveHistory(storage, entry(`run-${index}`, NOW + index), NOW + 32);
    }

    const saved = readHistory(storage, NOW + 32);
    expect(saved).toHaveLength(30);
    expect(saved[0].id).toBe("run-31");
    expect(saved[29].id).toBe("run-2");
  });

  it("physically removes expired snapshots at exactly 30 days", () => {
    const storage = new MemoryStorage();
    saveHistory(storage, entry("expired", NOW - 30 * DAY), NOW - 30 * DAY);
    saveHistory(
      storage,
      entry("current", NOW - 30 * DAY + 1),
      NOW - 30 * DAY + 1,
    );

    expect(readHistory(storage, NOW).map((item) => item.id)).toEqual([
      "current",
    ]);
    expect(storage.value).not.toContain("expired");
  });

  it("deletes only the requested snapshot", () => {
    const storage = new MemoryStorage();
    saveHistory(storage, entry("first"), NOW);
    saveHistory(storage, entry("second"), NOW);

    expect(deleteHistory(storage, "first", NOW).map((item) => item.id)).toEqual(
      ["second"],
    );
    expect(readHistory(storage, NOW).map((item) => item.id)).toEqual([
      "second",
    ]);
  });

  it.each(["broken JSON", "null", "[]", '{"version":99,"entries":[]}'])(
    "reports invalid stored content instead of hiding it as empty: %s",
    (value) => {
      const storage = new MemoryStorage();
      storage.value = value;
      expect(() => readHistory(storage, NOW)).toThrow(HistoryError);
      expect(storage.value).toBe(value);
    },
  );

  it("rejects malformed nested snapshots before the UI consumes them", () => {
    const storage = new MemoryStorage();
    saveHistory(storage, entry(), NOW);
    const raw = JSON.parse(storage.value!);
    raw.entries[0].products[0].matched = null;
    storage.value = JSON.stringify(raw);

    expect(() => readHistory(storage, NOW)).toThrow(HistoryError);
  });

  it.each([
    { mismatched: undefined },
    { mismatched: null },
    { mismatched: "テンキー付き" },
    { mismatched: [42] },
  ])(
    "rejects absent or malformed mismatch explanations: $mismatched",
    ({ mismatched }) => {
      const storage = new MemoryStorage();
      saveHistory(storage, entry(), NOW);
      const raw = JSON.parse(storage.value!);
      raw.entries[0].products[0].mismatched = mismatched;
      storage.value = JSON.stringify(raw);

      expect(() => readHistory(storage, NOW)).toThrow(HistoryError);
    },
  );

  it("preserves explicit mismatches without sharing arrays with the caller", () => {
    const storage = new MemoryStorage();
    const original = entry();
    original.products[0].mismatched = ["テンキー付き"];
    saveHistory(storage, original, NOW);
    original.products[0].mismatched.push("変更された説明");

    expect(readHistory(storage, NOW)[0].products[0].mismatched).toEqual([
      "テンキー付き",
    ]);
  });

  it("rejects external or traversal image URLs restored from storage", () => {
    for (const image of [
      "https://example.invalid/image.svg",
      "//example.invalid/image.svg",
      "/images/../secret.svg",
    ]) {
      const storage = new MemoryStorage();
      const invalid = entry();
      invalid.products[0].image = image;

      expect(() => saveHistory(storage, invalid, NOW)).toThrow(HistoryError);
      expect(storage.value).toBeNull();
    }
  });

  it("does not claim success or lose the prior entry after quota failure", () => {
    const storage = new MemoryStorage();
    saveHistory(storage, entry("saved"), NOW);
    const previous = storage.value;
    storage.failWrite = true;

    expect(() => saveHistory(storage, entry("unsaved"), NOW)).toThrow(
      "結果を履歴に保存できませんでした",
    );
    expect(storage.value).toBe(previous);
    expect(() => deleteHistory(storage, "saved", NOW)).toThrow(
      "履歴を削除できませんでした",
    );
    expect(storage.value).toBe(previous);
  });

  it("uses a safe fixed message when storage reads are unavailable", () => {
    const storage = new MemoryStorage();
    storage.failRead = true;

    expect(() => readHistory(storage, NOW)).toThrow(
      "検索履歴を読み込めませんでした",
    );
    expect(() => readHistory(storage, NOW)).not.toThrow(
      "private storage failure",
    );
  });

  it("does not pretend expired entries were removed when pruning cannot be saved", () => {
    const storage = new MemoryStorage();
    saveHistory(storage, entry(), NOW);
    storage.failWrite = true;

    expect(() => readHistory(storage, NOW + 30 * DAY)).toThrow(HistoryError);
  });
});
