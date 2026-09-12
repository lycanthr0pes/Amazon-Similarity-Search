import assert from "node:assert/strict";
import { test } from "node:test";
import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import {
  productDetails,
  searchProducts,
} from "../tools/playwright_product_dom.mjs";

test("offline search and detail extraction preserve product identity and observed attributes", async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      locale: "ja-JP",
      serviceWorkers: "block",
    });
    await context.route("**/*", (route) => route.abort());
    const page = await context.newPage();
    const card = (asin, linked = asin) =>
      `<div data-component-type="s-search-result" data-asin="${asin}"><h2>合成カップ</h2><a href="/dp/${linked}">詳細</a></div>`;
    await page.setContent(
      '<input id="twotabsearchtextbox" value="synthetic"><div class="s-main-slot">' +
        card("B000000001") +
        card("B000000001") +
        card("B000000002", "B000000099") +
        "</div>",
    );
    const found = await page.evaluate(searchProducts, 24);
    assert.equal(found.cardCount, 3);
    assert.equal(found.products.length, 1);
    assert.equal(found.products[0].asin, "B000000001");
    assert.equal(found.query, "synthetic");
    await page.setContent(
      '<h1 id="productTitle">合成カップ</h1><input name="ASIN" value="B000000001"><div id="corePriceDisplay_desktop_feature_div"><span class="a-price"><span class="a-offscreen">￥1,200</span></span><span class="a-price a-text-price"><span class="a-offscreen">￥9,999</span></span></div><div id="productDescription">合成の説明</div><div id="feature-bullets"><li><span class="a-list-item">合成特徴</span></li></div><table id="productDetails_techSpec_section_1"><tr><th>材質</th><td>陶器</td></tr><tr><th>容量</th><td>300 ml</td></tr></table><img id="landingImage" data-old-hires="https://m.media-amazon.com/synthetic.jpg">',
    );
    const observed = await page.evaluate(productDetails, "B000000001");
    assert.equal(observed.matched, true);
    assert.equal(observed.product.price, 1200);
    assert.equal(observed.product.currency, "JPY");
    assert.equal(observed.product.material, "陶器");
    assert.match(observed.product.description, /容量: 300 ml/);
    assert.deepEqual(observed.product.features, ["合成特徴"]);
    assert.equal(
      observed.product.image_1,
      "https://m.media-amazon.com/synthetic.jpg",
    );
    assert.equal(
      (await page.evaluate(productDetails, "B000000002")).matched,
      false,
    );
    await page.setContent('<input id="captchacharacters">');
    assert.equal(
      (await page.evaluate(productDetails, "B000000001")).challenge,
      true,
    );
    assert.equal((await page.evaluate(searchProducts, 24)).challenge, true);
    await context.close();
  } finally {
    await browser.close();
  }
});
