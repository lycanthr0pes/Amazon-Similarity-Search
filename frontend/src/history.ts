import type { Conditions, Product } from "./model";

export const HISTORY_KEY = "amazon-explorer.mock-history.v1";
export const HISTORY_TTL_MS = 30 * 24 * 60 * 60 * 1_000;
const HISTORY_LIMIT = 30;
const VERSION = 1;

export interface HistoryStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface HistoryEntry {
  id: string;
  createdAt: number;
  input: string;
  conditions: Conditions;
  useImages: boolean;
  products: Product[];
}

type Operation = "read" | "save" | "delete";

const MESSAGES: Record<Operation, string> = {
  read: "検索履歴を読み込めませんでした",
  save: "結果を履歴に保存できませんでした",
  delete: "履歴を削除できませんでした",
};

export class HistoryError extends Error {
  readonly operation: Operation;

  constructor(operation: Operation) {
    super(MESSAGES[operation]);
    this.name = "HistoryError";
    this.operation = operation;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.length <= 2_000;
}

function isTextList(value: unknown): value is string[] {
  return Array.isArray(value) && value.length <= 48 && value.every(isText);
}

function isConditions(value: unknown): value is Conditions {
  return (
    isRecord(value) &&
    ["product", "required", "preferred", "excluded", "budget"].every((key) =>
      isText(value[key]),
    )
  );
}

function isProduct(value: unknown): value is Product {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isText(value.id) &&
    value.id.length > 0 &&
    isText(value.name) &&
    typeof value.price === "number" &&
    Number.isFinite(value.price) &&
    value.price >= 0 &&
    typeof value.rating === "number" &&
    value.rating >= 0 &&
    value.rating <= 5 &&
    Number.isSafeInteger(value.reviews) &&
    (value.reviews as number) >= 0 &&
    typeof value.image === "string" &&
    /^\/images\/[a-zA-Z0-9][a-zA-Z0-9_-]*\.(svg|png|webp|jpe?g)$/.test(
      value.image,
    ) &&
    isTextList(value.matched) &&
    isTextList(value.unknown) &&
    isTextList(value.mismatched)
  );
}

function isEntry(value: unknown): value is HistoryEntry {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isText(value.id) &&
    value.id.length > 0 &&
    Number.isSafeInteger(value.createdAt) &&
    (value.createdAt as number) >= 0 &&
    isText(value.input) &&
    isConditions(value.conditions) &&
    typeof value.useImages === "boolean" &&
    Array.isArray(value.products) &&
    value.products.length <= 48 &&
    value.products.every(isProduct)
  );
}

function load(storage: HistoryStorage): HistoryEntry[] {
  const raw = storage.getItem(HISTORY_KEY);
  if (raw === null) {
    return [];
  }
  const parsed: unknown = JSON.parse(raw);
  if (
    !isRecord(parsed) ||
    parsed.version !== VERSION ||
    !Array.isArray(parsed.entries) ||
    !parsed.entries.every(isEntry)
  ) {
    throw new HistoryError("read");
  }
  const entries: HistoryEntry[] = parsed.entries;
  if (new Set(entries.map((entry) => entry.id)).size !== entries.length) {
    throw new HistoryError("read");
  }
  return entries;
}

function retained(entries: HistoryEntry[], now: number): HistoryEntry[] {
  if (!Number.isSafeInteger(now) || now < 0) {
    throw new HistoryError("read");
  }
  return entries
    .filter((entry) => now - entry.createdAt < HISTORY_TTL_MS)
    .sort((left, right) => right.createdAt - left.createdAt)
    .slice(0, HISTORY_LIMIT);
}

function store(
  storage: HistoryStorage,
  entries: HistoryEntry[],
): HistoryEntry[] {
  const serialized = JSON.stringify({ version: VERSION, entries });
  storage.setItem(HISTORY_KEY, serialized);
  return JSON.parse(serialized).entries as HistoryEntry[];
}

export function readHistory(
  storage: HistoryStorage,
  now: number,
): HistoryEntry[] {
  try {
    const entries = load(storage);
    const current = retained(entries, now);
    if (current.length !== entries.length) {
      return store(storage, current);
    }
    return current;
  } catch {
    throw new HistoryError("read");
  }
}

export function saveHistory(
  storage: HistoryStorage,
  entry: HistoryEntry,
  now: number,
): HistoryEntry[] {
  try {
    if (!isEntry(entry)) {
      throw new HistoryError("save");
    }
    const entries = readHistory(storage, now);
    if (entries.some((existing) => existing.id === entry.id)) {
      return entries;
    }
    return store(storage, retained([entry, ...entries], now));
  } catch {
    throw new HistoryError("save");
  }
}

export function deleteHistory(
  storage: HistoryStorage,
  id: string,
  now: number,
): HistoryEntry[] {
  try {
    const entries = readHistory(storage, now);
    return store(
      storage,
      entries.filter((entry) => entry.id !== id),
    );
  } catch {
    throw new HistoryError("delete");
  }
}
