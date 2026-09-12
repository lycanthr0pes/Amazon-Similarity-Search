import { parseSearchView, type SearchView } from "./connected-api";

export interface HistoryItem {
  id: string;
  summary: string;
  productName?: string;
  completedAt: string;
  expiresAt: string;
  count: number;
}
export interface HistoryDetail extends HistoryItem {
  view: SearchView;
}
export class HistoryUnavailable extends Error {}

function parseItem(value: unknown): HistoryItem {
  const item = value as HistoryItem;
  if (
    !item ||
    typeof item !== "object" ||
    typeof item.id !== "string" ||
    !/^[A-Za-z0-9_-]{43,128}$/.test(item.id) ||
    typeof item.summary !== "string" ||
    !item.summary.trim() ||
    item.summary.length > 500 ||
    (item.productName !== undefined &&
      (typeof item.productName !== "string" ||
        !item.productName.trim() ||
        Array.from(item.productName).length > 100 ||
        /[\u0000-\u001f\u007f]/.test(item.productName))) ||
    typeof item.completedAt !== "string" ||
    !Number.isFinite(Date.parse(item.completedAt)) ||
    typeof item.expiresAt !== "string" ||
    !Number.isFinite(Date.parse(item.expiresAt)) ||
    Date.parse(item.expiresAt) <= Date.parse(item.completedAt) ||
    !Number.isInteger(item.count) ||
    item.count < 0 ||
    item.count > 48
  )
    throw new Error("Invalid history item");
  return item;
}
export function historyProductName(item: HistoryItem): string {
  if (item.productName) return item.productName;
  // Older histories kept only the request summary. Use a standalone leading
  // product phrase; do not present a sentence of conditions as a product name.
  const first = item.summary.split(/[。\r\n]/)[0].trim();
  return first &&
    Array.from(first).length <= 100 &&
    !/[、,，]|[0-9０-９]+\s*(?:円|万円)|以上|以下|以内|できれば|なるべく|希望|避け|不要|こだわ|探し|探す|欲しい|ほしい/.test(
      first,
    )
    ? first
    : "商品名未保存";
}

async function get(path: string): Promise<unknown> {
  const response = await fetch(path, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (response.status === 404) throw new HistoryUnavailable();
  if (!response.ok) throw new Error("History unavailable");
  return response.json();
}
export async function readHistoryState(): Promise<{
  items: HistoryItem[];
  cleanupPending: boolean;
}> {
  const data = (await get("/api/history")) as {
    items: unknown[];
    cleanupPending?: boolean;
  };
  if (!data || !Array.isArray(data.items) || data.items.length > 30)
    throw new Error("Invalid history list");
  const items = data.items.map(parseItem);
  if (new Set(items.map((i) => i.id)).size !== items.length)
    throw new Error("Duplicate history item");
  if (
    data.cleanupPending !== undefined &&
    typeof data.cleanupPending !== "boolean"
  )
    throw new Error("Invalid history cleanup state");
  return { items, cleanupPending: data.cleanupPending === true };
}
export async function readHistory(): Promise<HistoryItem[]> {
  return (await readHistoryState()).items;
}
export async function readHistoryDetail(id: string): Promise<HistoryDetail> {
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(id)) throw new HistoryUnavailable();
  const data = (await get(
    "/api/history/" + encodeURIComponent(id),
  )) as HistoryDetail;
  const item = parseItem(data);
  const view = parseSearchView(data.view, 48);
  if (
    item.id !== id ||
    view.stage !== "complete" ||
    view.saved !== true ||
    view.products?.length !== item.count
  )
    throw new Error("Invalid saved result");
  return { ...item, view };
}

async function mutate(command: object): Promise<Record<string, unknown>> {
  const response = await fetch("/api/history/command", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Amazon-Explorer-Browser": "1",
    },
    body: JSON.stringify(command),
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error("History change failed");
  return response.json();
}
export async function deleteHistory(id: string): Promise<void> {
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(id)) throw new HistoryUnavailable();
  const result = await mutate({ action: "delete", id, confirmed: true });
  if (result?.deleted !== true) throw new Error("History deletion unconfirmed");
}
export async function purgeExpiredHistory(): Promise<void> {
  const result = await mutate({ action: "purge_expired" });
  if (
    !Number.isInteger(result?.deletedCount) ||
    (result.deletedCount as number) < 0
  )
    throw new Error("History cleanup unconfirmed");
}
