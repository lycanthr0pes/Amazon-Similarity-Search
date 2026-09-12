import { afterEach, expect, it, vi } from "vitest";
import {
  readHistory,
  readHistoryDetail,
  HistoryUnavailable,
  historyProductName,
} from "./connected-history-api";
const id = "h".repeat(43);
const item = {
  id,
  summary: "合成履歴",
  completedAt: "2026-09-12T00:00:00Z",
  expiresAt: "2026-10-12T00:00:00Z",
  count: 1,
};
function respond(body: unknown, status = 200) {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: status === 200, status, json: async () => body });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
afterEach(() => vi.unstubAllGlobals());
it("rejects invalid locators before sending and duplicated list entries", async () => {
  const fetcher = respond({ items: [item, item] });
  await expect(
    readHistoryDetail("../../private.sqlite3"),
  ).rejects.toBeInstanceOf(HistoryUnavailable);
  expect(fetcher).not.toHaveBeenCalled();
  await expect(readHistory()).rejects.toThrow("Duplicate");
});
it("distinguishes a missing history from an unavailable database", async () => {
  respond({}, 404);
  await expect(readHistoryDetail(id)).rejects.toBeInstanceOf(
    HistoryUnavailable,
  );
  respond({}, 503);
  await expect(readHistory()).rejects.toThrow("History unavailable");
});
it("requires matching saved results and validates external links", async () => {
  const product = {
    title: "合成の商品",
    price: 1000,
    url: null,
    required: "一致",
    appearance: "外観は未確認",
  };
  const view = {
    stage: "complete",
    revision: 0,
    saved: true,
    products: [product],
  };
  respond({ ...item, view });
  expect((await readHistoryDetail(id)).view.products).toHaveLength(1);
  respond({ ...item, count: 2, view });
  await expect(readHistoryDetail(id)).rejects.toThrow("Invalid saved result");
  respond({
    ...item,
    view: {
      ...view,
      products: [{ ...product, url: "https://example.com/tracker" }],
    },
  });
  await expect(readHistoryDetail(id)).rejects.toThrow();
  respond({
    ...item,
    count: 48,
    view: { ...view, products: Array.from({ length: 48 }, () => product) },
  });
  expect((await readHistoryDetail(id)).view.products).toHaveLength(48);
});

it("deletes only a validated locator with explicit confirmation and never retries automatically", async () => {
  const { deleteHistory } = await import("./connected-history-api");
  const fetcher = respond({ deleted: true });
  await expect(deleteHistory("../history.sqlite3")).rejects.toBeInstanceOf(
    HistoryUnavailable,
  );
  expect(fetcher).not.toHaveBeenCalled();
  await deleteHistory(id);
  expect(fetcher).toHaveBeenCalledTimes(1);
  const [path, options] = fetcher.mock.calls[0];
  expect(path).toBe("/api/history/command");
  expect(JSON.parse(options.body)).toEqual({
    action: "delete",
    id,
    confirmed: true,
  });
  fetcher.mockResolvedValue({ ok: false, status: 503 });
  await expect(deleteHistory(id)).rejects.toThrow();
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("validates cleanup responses without sending owner, paths, or a client clock", async () => {
  const { purgeExpiredHistory, readHistoryState } =
    await import("./connected-history-api");
  const fetcher = respond({ deletedCount: 0 });
  await purgeExpiredHistory();
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    action: "purge_expired",
  });
  respond({ deletedCount: -1 });
  await expect(purgeExpiredHistory()).rejects.toThrow();
  respond({ items: [], cleanupPending: true });
  expect(await readHistoryState()).toEqual({ items: [], cleanupPending: true });
  respond({ items: [], cleanupPending: "true" });
  await expect(readHistoryState()).rejects.toThrow();
});

it("restores full input and source-bound labels while rejecting incomplete snapshots", async () => {
  const view = {
    stage: "complete",
    revision: 0,
    saved: true,
    input: "合成😀。取っ手がなくてもよい。",
    historyContentAvailable: true,
    conditionLabels: { "condition-price": "3000円以下" },
    conditionReview: [
      {
        start: 4,
        end: 14,
        quote: "取っ手がなくてもよい",
        target: "取っ手",
        strength: "neutral",
        reason: "permission",
      },
    ],
    products: [],
    imageMode: "off",
    images: [],
  };
  respond({ ...item, count: 0, view });
  const saved = await readHistoryDetail(id);
  expect(saved.view.input).toBe(view.input);
  expect(saved.view.conditionLabels).toEqual(view.conditionLabels);
  for (const extra of [
    { input: "あ".repeat(2001) },
    { input: "別の原文" },
    { historyContentAvailable: "true" },
    { conditionLabels: undefined },
  ]) {
    respond({ ...item, count: 0, view: { ...view, ...extra } });
    await expect(readHistoryDetail(id)).rejects.toThrow();
  }
});

it("shows a saved product name and conservatively reads older leading product phrases", () => {
  expect(
    historyProductName({
      ...item,
      productName: "マグカップ",
      summary: "3000円以下の商品を探しています。",
    }),
  ).toBe("マグカップ");
  expect(
    historyProductName({
      ...item,
      summary: "マグカップ。丸みのある形。3000円以下。",
    }),
  ).toBe("マグカップ");
  expect(
    historyProductName({
      ...item,
      summary: "3000円以下のマグカップを探しています。",
    }),
  ).toBe("商品名未保存");
});
it("validates the optional product name while keeping the original summary", async () => {
  respond({ items: [{ ...item, productName: "マグカップ" }] });
  expect((await readHistory())[0]).toMatchObject({
    productName: "マグカップ",
    summary: item.summary,
  });
  for (const productName of ["", "あ".repeat(101), 42, null, "合成\n商品"]) {
    respond({ items: [{ ...item, productName }] });
    await expect(readHistory()).rejects.toThrow("Invalid history item");
  }
});
