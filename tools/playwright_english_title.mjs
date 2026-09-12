import { productDetails } from "./playwright_product_dom.mjs";

// Optional observation: failures never replace the primary Japanese product.
export async function fetchEnglishTitle(
  context,
  asin,
  metrics,
  openPage,
  includeDetails = false,
) {
  const missing = {
    name_en: null,
    title_en_status: "unavailable",
    challenge: false,
    ...(includeDetails ? { details_en_status: "unavailable" } : {}),
  };
  let page;
  try {
    page = await openPage(
      context,
      `https://www.amazon.co.jp/dp/${asin}?language=en_US`,
      metrics,
    );
    try {
      await page
        .locator("#productTitle, #captchacharacters")
        .first()
        .waitFor({ state: "attached", timeout: 5000 });
    } catch {
      // Inspect the received page once; do not retry or infer missing content.
    }
    const observed = await page.evaluate(productDetails, asin);
    if (observed.challenge) return { ...missing, challenge: true };
    const name = observed.product.name;
    const details =
      includeDetails &&
      observed.matched &&
      /^en(?:[-_]|$)/i.test(observed.language || "")
        ? {
            details_en_status: "available",
            description_en: observed.product.description,
            features_en: observed.product.features,
            color_en: observed.product.color,
            material_en: observed.product.material,
          }
        : {};

    if (
      !observed.matched ||
      !/^en(?:[-_]|$)/i.test(observed.language || "") ||
      typeof name !== "string" ||
      !/[a-z]/i.test(name) ||
      /[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}]/u.test(name)
    ) {
      return { ...missing, ...details };
    }
    return {
      name_en: name,
      title_en_status: "available",
      challenge: false,
      ...details,
    };
  } catch {
    return missing;
  } finally {
    if (page) {
      try {
        await page.close();
      } catch {
        // The owning worker still closes the context and browser at completion.
      }
    }
  }
}
