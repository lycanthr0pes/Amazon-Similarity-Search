import assert from "node:assert/strict";
import test from "node:test";
import { fetchEnglishTitle } from "../tools/playwright_english_title.mjs";
import { collect } from "../tools/playwright_products_collect.mjs";

const observed = (overrides = {}) => ({
  matched: true,
  challenge: false,
  language: "en-US",
  product: { name: "Synthetic Ceramic Mug" },
  ...overrides,
});

test("English details survive an untranslated title without another page request", async () => {
  let calls = 0;
  const result = await fetchEnglishTitle(
    {},
    "B000000001",
    {},
    async () => {
      calls++;
      return {
        locator: () => ({ first: () => ({ waitFor: async () => {} }) }),
        evaluate: async () =>
          observed({
            product: {
              name: "合成マグ",
              description: "Microwave safe.",
              features: ["Capacity: 500 ml"],
              color: "White",
              material: "Ceramic",
            },
          }),
        close: async () => {},
      };
    },
    true,
  );
  assert.equal(calls, 1);
  assert.equal(result.title_en_status, "unavailable");
  assert.equal(result.details_en_status, "available");
  assert.equal(result.description_en, "Microwave safe.");
  assert.deepEqual(result.features_en, ["Capacity: 500 ml"]);
});

test("English detail observations cannot cross an ASIN or language mismatch", async () => {
  for (const value of [
    observed({ matched: false }),
    observed({ language: "ja-JP" }),
    observed({ challenge: true }),
  ]) {
    const result = await fetchEnglishTitle(
      {},
      "B000000001",
      {},
      async () => ({
        locator: () => ({ first: () => ({ waitFor: async () => {} }) }),
        evaluate: async () => value,
        close: async () => {},
      }),
      true,
    );
    assert.equal(result.details_en_status, "unavailable");
    assert.equal(result.description_en, undefined);
  }
});

test("English observation requires a matching product, English page and translated title", async () => {
  for (const [value, available] of [
    [observed(), true],
    [observed({ matched: false }), false],
    [observed({ language: "ja-JP" }), false],
    [observed({ product: { name: "合成マグカップ" } }), false],
    [observed({ product: { name: "" } }), false],
  ]) {
    let closed = 0;
    const page = {
      locator: () => ({ first: () => ({ waitFor: async () => {} }) }),
      evaluate: async () => value,
      close: async () => {
        closed++;
      },
    };
    const result = await fetchEnglishTitle(
      {},
      "B000000001",
      {},
      async () => page,
    );
    assert.equal(
      result.title_en_status,
      available ? "available" : "unavailable",
    );
    assert.equal(result.name_en, available ? value.product.name : null);
    assert.equal(closed, 1);
  }
});

test("optional English failure retains a missing observation and closes its page", async () => {
  const failed = await fetchEnglishTitle({}, "B000000001", {}, async () => {
    throw Error("private");
  });
  assert.deepEqual(failed, {
    name_en: null,
    title_en_status: "unavailable",
    challenge: false,
  });
  const challenge = await fetchEnglishTitle({}, "B000000001", {}, async () => ({
    locator: () => ({ first: () => ({ waitFor: async () => {} }) }),
    evaluate: async () => observed({ challenge: true }),
    close: async () => {},
  }));
  assert.equal(challenge.challenge, true);
  assert.equal(challenge.name_en, null);
});

test("a challenge stops additional English pages while Japanese products and deduplication survive", async () => {
  const ja = {},
    en = {};
  const calls = [],
    events = [];
  const metrics = { search_pages: 0, detail_pages: 0, english_detail_pages: 0 };
  const products = ["B000000001", "B000000002"].map((asin) => ({ asin }));
  const result = await collect(
    ja,
    en,
    { queries: ["合成", "synthetic"], limit: 2, englishTitles: true },
    metrics,
    {
      emit: (event) => events.push(event),
      openPage: async (context, target) => {
        calls.push({ context, target });
        const query = new URL(target).searchParams.get("k");
        return {
          locator: () => ({ first: () => ({ waitFor: async () => {} }) }),
          evaluate: async () =>
            query
              ? { query, cardCount: 2, products, next: false, challenge: false }
              : context === en
                ? observed({ challenge: true })
                : observed({ product: { name: "合成商品" } }),
          close: async () => {},
        };
      },
    },
  );
  assert.equal(calls.filter((call) => call.context === en).length, 1);
  assert.equal(metrics.detail_pages, 2);
  assert.equal(metrics.english_detail_pages, 1);
  assert.equal(events.length, 7);
  assert.deepEqual(events[2], { event: "progress", phase: "details" });
  assert.ok(calls.slice(0, 2).every(call => new URL(call.target).pathname === "/s"));
  assert.deepEqual(
    result.data.map((group) => group.length),
    [2, 2],
  );
  assert.ok(
    result.data
      .flat()
      .every(
        (product) =>
          product.name === "合成商品" &&
          product.name_en === null &&
          product.title_en_status === "unavailable",
      ),
  );
});
