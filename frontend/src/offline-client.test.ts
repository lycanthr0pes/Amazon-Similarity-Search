import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { createOfflineClient } from "./offline-client";
import { OFFLINE_HISTORY_KEY } from "./offline-history";
import type { SearchClient } from "./search-client";
import type { HistoryStorage } from "./history";

let storage: HistoryStorage;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-13T00:00:00Z"));
  const data = new Map<string, string>();
  storage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value);
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      throw new Error("Network forbidden");
    }),
  );
});
afterEach(() => {
  expect(fetch).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
async function command(client: SearchClient, action: string, values = {}) {
  return client.sendSearch(action, await client.readSearch(), values);
}
async function settle(client: SearchClient, milliseconds = 2500) {
  vi.advanceTimersByTime(milliseconds);
  return client.readSearch();
}
async function prepare(client: SearchClient, imageMode = "off") {
  await command(client, "start", {
    source: "合成の入力。キーボード。",
    imageMode,
  });
  return settle(client);
}
async function complete(client: SearchClient) {
  await prepare(client);
  await command(client, "without_images");
  await command(client, "search");
  for (let i = 0; i < 5; i += 1) {
    await settle(client);
  }
  return client.readSearch();
}

test("image-free completion keeps thumbnails and scores in reloadable tab history", async () => {
  const client = createOfflineClient(() => storage);
  const view = await complete(client);
  expect(view.stage).toBe("complete");
  expect(view.saved).toBe(true);
  expect(view.products).toHaveLength(12);
  expect(view.products?.[0].thumbnail).toBe("/images/keyboard-white.svg");
  expect(
    view.products?.every((p) => p.scores?.image === null && p.url === null),
  ).toBe(true);
  expect(view.images).toEqual([]);
  const reopened = createOfflineClient(() => storage);
  expect((await reopened.readSearch()).stage).toBe("idle");
  const { items } = await reopened.readHistoryState();
  expect(items).toHaveLength(1);
  expect((await reopened.readHistoryDetail(items[0].id)).view.products).toEqual(
    view.products,
  );
});

test("three preparations bound image enabling and preserve edited groups", async () => {
  const client = createOfflineClient(() => storage);
  expect((await prepare(client)).imageMode).toBe("off");
  await command(client, "reference");
  expect((await client.readSearch()).stage).toBe("query");
  await command(client, "revise", {
    source: "合成商品。軽い。できれば青。大型は避けたい。",
    imageMode: "on",
  });
  let view = await settle(client);
  expect(view.imageMode).toBeUndefined();
  expect(view.productName).toBe("合成商品");
  expect(view.conditionReview?.map((r) => r.strength)).toEqual([
    "required",
    "preferred",
    "excluded",
  ]);
  await command(client, "revise", { source: view.input, imageMode: "on" });
  view = await settle(client);
  expect(view.canRevise).toBe(false);
  expect(view.productName).toBe("合成商品");
  expect(view.conditionReview?.map((r) => r.target)).toEqual([
    "軽い",
    "青",
    "大型",
  ]);
  await command(client, "revise", { source: "another", imageMode: "on" });
  expect((await client.readSearch()).revision).toBe(view.revision);
});

test("separate approvals and shared two-set image limit match production", async () => {
  const client = createOfflineClient(() => storage);
  await prepare(client, "on");
  await command(client, "reference", { prompt: "Edited reference" });
  let view = await settle(client);
  expect(view.stage).toBe("reference");
  expect(view.images).toHaveLength(1);
  expect(view.referenceRemaining).toBe(1);
  await command(client, "search");
  expect((await client.readSearch()).stage).toBe("reference");
  await command(client, "comparison", {
    prompts: { color: "Edited color", shape: "Edited shape" },
  });
  view = await settle(client);
  expect(view.images).toHaveLength(3);
  const reference = view.images?.[0];
  await command(client, "regenerate_comparisons", {
    prompts: { color: "Second color", shape: "Second shape" },
  });
  view = await settle(client);
  expect(view.images?.[0]).toBe(reference);
  expect(view.imagePrompts?.comparison.color).toBe("Second color");
  expect(view.referenceRemaining).toBe(0);
  expect(view.canRegenerate).toBe(false);
  await command(client, "final");
  expect((await client.readSearch()).stage).toBe("final");
});

test("busy reset and stale duplicate commands cannot discard or repeat a search", async () => {
  const client = createOfflineClient(() => storage);
  await prepare(client);
  await command(client, "without_images");
  const before = await client.readSearch();
  await client.sendSearch("search", before);
  await client.sendSearch("search", before);
  await command(client, "reset");
  expect((await client.readSearch()).stage).toBe("working");
  for (let i = 0; i < 5; i += 1) {
    await settle(client);
  }
  expect((await client.readHistoryState()).items).toHaveLength(1);
});

test("cancel waits for current acquisition and creates no history", async () => {
  const client = createOfflineClient(() => storage);
  await prepare(client);
  await command(client, "without_images");
  await command(client, "search");
  const view = await command(client, "cancel");
  expect(view.stage).toBe("working");
  expect(view.cancelRequested).toBe(true);
  expect((await settle(client)).stage).toBe("cancelled");
  expect((await client.readHistoryState()).items).toHaveLength(0);
});

test("save-only retry stores once and does not restart research", async () => {
  const client = createOfflineClient(() => storage, "save-error");
  expect((await complete(client)).canRetrySave).toBe(true);
  expect((await client.readHistoryState()).items).toHaveLength(0);
  const completedAt = new Date().toISOString();
  vi.advanceTimersByTime(60_000);
  const view = await command(client, "retry_save");
  expect(view.stage).toBe("complete");
  expect(view.saved).toBe(true);
  expect((await client.readHistoryState()).items[0].completedAt).toBe(
    completedAt,
  );
  await command(client, "retry_save");
  expect((await client.readHistoryState()).items).toHaveLength(1);
});

test("delete failure retains history until retry and expiry hides old entries", async () => {
  const client = createOfflineClient(() => storage, "delete-error");
  await complete(client);
  const { items } = await client.readHistoryState();
  await expect(client.deleteHistory(items[0].id)).rejects.toThrow();
  expect((await client.readHistoryState()).items).toHaveLength(1);
  await client.deleteHistory(items[0].id);
  expect((await client.readHistoryState()).items).toHaveLength(0);
  await command(client, "reset");
  await complete(client);
  vi.advanceTimersByTime(30 * 24 * 60 * 60_000);
  expect((await client.readHistoryState()).items).toHaveLength(0);
  await client.purgeExpiredHistory();
  expect(JSON.parse(storage.getItem(OFFLINE_HISTORY_KEY)!)).toEqual([]);
});

test("corrupt saved URLs cannot initiate external image requests", async () => {
  const client = createOfflineClient(() => storage);
  await complete(client);
  const entries = JSON.parse(storage.getItem(OFFLINE_HISTORY_KEY)!);
  entries[0].view.products[0].thumbnail = "https://example.com/image.png";
  storage.setItem(OFFLINE_HISTORY_KEY, JSON.stringify(entries));
  await expect(client.readHistoryState()).rejects.toThrow(
    "Invalid offline history",
  );
});

test("expired image confirmation permits image-free recovery but prevents approval", async () => {
  const client = createOfflineClient(() => storage);
  await prepare(client, "on");
  await command(client, "reference");
  await settle(client);
  let view = await settle(client, 15 * 60_000);
  expect(view.stage).toBe("expired");
  await command(client, "comparison");
  expect((await client.readSearch()).stage).toBe("expired");
  view = await command(client, "without_images");
  expect(view.stage).toBe("final");
  expect(view.images).toEqual([]);
});

test("unresolved attributes require selection before ranking", async () => {
  const client = createOfflineClient(() => storage, "attributes");
  await prepare(client);
  await command(client, "without_images");
  await command(client, "search");
  await settle(client);
  expect((await settle(client)).stage).toBe("attributes");
  await command(client, "rank", { selections: {} });
  expect((await client.readSearch()).stage).toBe("attributes");
  await command(client, "rank", { selections: { connection: "wireless" } });
  for (let i = 0; i < 3; i += 1) {
    await settle(client);
  }
  expect((await client.readSearch()).saved).toBe(true);
});

test("expiry cleanup failure hides expired data and exposes retry without search", async () => {
  const client = createOfflineClient(() => storage);
  await complete(client);
  const original = storage.setItem;
  storage.setItem = () => {
    throw new Error("Storage unavailable");
  };
  vi.advanceTimersByTime(30 * 24 * 60 * 60_000);
  expect(await client.readHistoryState()).toEqual({
    items: [],
    cleanupPending: true,
  });
  await expect(client.purgeExpiredHistory()).rejects.toThrow();
  storage.setItem = original;
  await client.purgeExpiredHistory();
  expect(await client.readHistoryState()).toEqual({
    items: [],
    cleanupPending: false,
  });
});
