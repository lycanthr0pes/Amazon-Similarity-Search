import { productDetails, searchProducts } from "./playwright_product_dom.mjs";
import { fetchEnglishTitle } from "./playwright_english_title.mjs";

const MAX_SEARCH_PAGES = 3;

export async function collect(
  context,
  englishContext,
  input,
  metrics,
  { openPage, emit },
) {
  const groups = [];
  const selections = [];
  const details = new Map();
  let englishChallenge = false;
  for (const query of input.queries) {
    const selected = new Set();
    for (
      let index = 1;
      index <= MAX_SEARCH_PAGES && selected.size < input.limit;
      index++
    ) {
      const target = new URL("https://www.amazon.co.jp/s");
      target.searchParams.set("k", query);
      target.searchParams.set("language", "ja_JP");
      if (index > 1) {
        target.searchParams.set("page", String(index));
      }
      metrics.search_pages++;
      const page = await openPage(context, target.href, metrics);
      try {
        await page
          .locator(
            '.s-main-slot [data-component-type="s-search-result"], #captchacharacters, .s-no-outline',
          )
          .first()
          .waitFor({ state: "attached", timeout: 5000 });
      } catch {
        // Inspect the received page before deciding between an empty result and an invalid page.
      }
      const found = await page.evaluate(searchProducts, input.limit);
      await page.close();
      if (found.challenge) {
        throw new Error("challenge");
      }
      if (found.query !== query || (!found.cardCount && !found.empty)) {
        throw new Error("search_contract");
      }
      for (const product of found.products) {
        if (selected.size < input.limit) {
          selected.add(product.asin);
        }
      }
      emit({ event: "progress" });
      if (!found.next) {
        break;
      }
    }
    selections.push({ query, selected });
  }
  emit({ event: "progress", phase: "details" });
  for (const { query, selected } of selections) {
    const products = [];
    for (const asin of selected) {
      if (!details.has(asin)) {
        metrics.detail_pages++;
        const page = await openPage(
          context,
          `https://www.amazon.co.jp/dp/${asin}?language=ja_JP`,
          metrics,
        );
        try {
          await page
            .locator("#productTitle, #captchacharacters")
            .first()
            .waitFor({ state: "attached", timeout: 5000 });
        } catch {
          // A missing title is rejected below, without exposing page content.
        }
        const observed = await page.evaluate(productDetails, asin);
        await page.close();
        if (observed.challenge) {
          throw new Error("challenge");
        }
        if (!observed.matched || !observed.product.name) {
          throw new Error("product_contract");
        }
        details.set(asin, observed.product);
        emit({ event: "progress" });
        if (input.englishTitles) {
          let english = {
            name_en: null,
            title_en_status: "unavailable",
            ...(input.englishDetails
              ? { details_en_status: "unavailable" }
              : {}),
          };
          if (!englishChallenge) {
            metrics.english_detail_pages++;
            const result = await fetchEnglishTitle(
              englishContext,
              asin,
              metrics,
              openPage,
              input.englishDetails,
            );
            englishChallenge = result.challenge;
            const { challenge, ...fields } = result;
            english = fields;
          }
          Object.assign(observed.product, english);
          emit({ event: "progress" });
        }
      }
      products.push({
        ...details.get(asin),
        query,
        position: products.length + 1,
      });
    }
    groups.push(products);
  }
  return { data: groups, metrics };
}
