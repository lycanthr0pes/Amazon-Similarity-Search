// These functions execute inside an untrusted page and return observations only.
export function searchProducts(limit) {
  const cards = [
    ...document.querySelectorAll(
      '.s-main-slot [data-component-type="s-search-result"][data-asin]',
    ),
  ];
  const products = [];
  const seen = new Set();
  for (const card of cards) {
    const asin = card.getAttribute("data-asin") || "";
    if (!/^[A-Z0-9]{10}$/.test(asin) || seen.has(asin)) {
      continue;
    }
    const title = card.querySelector("h2")?.textContent?.trim();
    let matched = false;
    for (const a of card.querySelectorAll("a[href]")) {
      try {
        let url = new URL(a.getAttribute("href"), "https://www.amazon.co.jp");
        if (url.searchParams.has("url")) {
          url = new URL(
            url.searchParams.get("url"),
            "https://www.amazon.co.jp",
          );
        }
        if (
          url.protocol !== "https:" ||
          url.username ||
          url.password ||
          url.port ||
          !(
            url.hostname === "amazon.co.jp" ||
            url.hostname.endsWith(".amazon.co.jp")
          )
        ) {
          continue;
        }
        const linked = url.pathname.match(
          /\/(?:dp|product)\/([A-Z0-9]{10})(?:[/?]|$)/,
        )?.[1];
        matched ||= linked === asin;
      } catch {
        // A malformed optional link is not an eligible product destination.
      }
    }
    if (!title || !matched) {
      continue;
    }
    seen.add(asin);
    products.push({ asin });
    if (products.length === limit) {
      break;
    }
  }
  const body = document.body?.textContent || "";
  return {
    products,
    cardCount: cards.length,
    query: document.querySelector("#twotabsearchtextbox")?.value,
    next: Boolean(document.querySelector("a.s-pagination-next")),
    empty:
      /一致する商品が見つかりません|検索結果はありません|did not match any products|No results for/i.test(
        body,
      ),
    challenge:
      Boolean(
        document.querySelector(
          '#captchacharacters, form[action*="validateCaptcha"]',
        ),
      ) || /robot check|automated access/i.test(body),
  };
}

export function productDetails(expectedAsin) {
  const text = (selector, max = 10000) =>
    document.querySelector(selector)?.textContent?.trim().slice(0, max) || null;
  const values = [
    ...document.querySelectorAll('input[name="ASIN"], #ASIN'),
  ].map((el) => el.value);
  const canonical = document.querySelector('link[rel="canonical"]')?.href || "";
  const canonicalAsin = canonical.match(
    /\/(?:dp|product)\/([A-Z0-9]{10})(?:[/?]|$)/,
  )?.[1];
  const matched = values.length
    ? values.includes(expectedAsin)
    : canonicalAsin === expectedAsin;
  const name = text("#productTitle", 4096);
  const specSelectors = [
    "#productOverview_feature_div tr",
    "#productDetails_techSpec_section_1 tr",
    "#productDetails_techSpec_section_2 tr",
    "#productDetails_detailBullets_sections1 tr",
  ];
  const specs = new Map();
  for (const selector of specSelectors) {
    for (const row of document.querySelectorAll(selector)) {
      const cells = row.querySelectorAll("th, td");
      if (cells.length === 2) {
        const key = cells[0].textContent.trim().slice(0, 100);
        const value = cells[1].textContent.trim().slice(0, 2000);
        if (key && value && !specs.has(key) && specs.size < 60) {
          specs.set(key, value);
        }
      }
    }
  }
  const features = [
    ...document.querySelectorAll("#feature-bullets li .a-list-item"),
  ]
    .map((el) => el.textContent.trim().slice(0, 2000))
    .filter(Boolean)
    .slice(0, 20);
  const details = [
    ...document.querySelectorAll("#detailBullets_feature_div li .a-list-item"),
  ]
    .map((el) => el.textContent.trim().slice(0, 2000))
    .filter(Boolean)
    .slice(0, 20);
  const attributes = [...specs].map(([key, value]) => `${key}: ${value}`);
  const priceSelectors = [
    "#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen",
    "#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    "#apex_desktop .a-price:not(.a-text-price) .a-offscreen",
  ];
  const priceText = priceSelectors.map((s) => text(s, 100)).find(Boolean) || "";
  const amount = priceText
    .normalize("NFKC")
    .match(/(?:¥|JPY\s*)([\d,]+)(?:\.\d+)?|([\d,]+)\s*円/);
  const price = amount
    ? Number((amount[1] || amount[2]).replaceAll(",", ""))
    : null;
  const img = document.querySelector("#landingImage, #imgBlkFront");
  const images = [
    img?.getAttribute("data-old-hires"),
    img?.getAttribute("src"),
  ];
  if (img?.hasAttribute("data-a-dynamic-image")) {
    try {
      images.push(
        ...Object.keys(JSON.parse(img.getAttribute("data-a-dynamic-image"))),
      );
    } catch {
      // The static image attributes remain usable if optional dynamic metadata is invalid.
    }
  }
  const safeImages = [
    ...new Set(
      images.filter((value) => {
        try {
          const url = new URL(value);
          return (
            url.protocol === "https:" &&
            !url.username &&
            !url.password &&
            !url.port &&
            ["media-amazon.com", "ssl-images-amazon.com"].some(
              (host) =>
                url.hostname === host || url.hostname.endsWith("." + host),
            )
          );
        } catch {
          return false;
        }
      }),
    ),
  ].slice(0, 10);
  const description = [text("#productDescription"), ...attributes, ...details]
    .filter(Boolean)
    .join("\n");
  const ratingText = text("#acrPopover .a-icon-alt", 100) || "";
  const ratingMatch = ratingText.match(
    /5つ星のうち\s*([\d.]+)|([\d.]+)\s*out of 5/,
  );
  const reviewText = text("#acrCustomerReviewText", 100) || "";
  const reviews = reviewText.match(/([\d,]+)\s*(?:個|件|ratings|reviews)/i);
  const body = document.body?.textContent || "";
  return {
    matched,
    language: document.documentElement.lang,
    challenge:
      Boolean(
        document.querySelector(
          '#captchacharacters, form[action*="validateCaptcha"]',
        ),
      ) ||
      (!name && /robot check|automated access/i.test(body)),
    product: {
      asin: expectedAsin,
      name,
      price: Number.isFinite(price) && price > 0 ? price : null,
      currency: amount ? "JPY" : null,
      description: description || null,
      features,
      brand: specs.get("ブランド") || specs.get("Brand") || null,
      color:
        specs.get("色") || specs.get("カラー") || specs.get("Color") || null,
      material:
        specs.get("材質") || specs.get("素材") || specs.get("Material") || null,
      store_title: text("#bylineInfo", 1000),
      categories: [
        ...document.querySelectorAll("#wayfinding-breadcrumbs_feature_div a"),
      ]
        .map((el) => el.textContent.trim())
        .filter(Boolean)
        .slice(0, 12),
      rating: ratingMatch ? Number(ratingMatch[1] || ratingMatch[2]) : null,
      reviews: reviews ? Number(reviews[1].replaceAll(",", "")) : null,
      availability: text("#availability", 1000),
      shipping: text(
        "#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE",
        1000,
      ),
      url: `https://www.amazon.co.jp/dp/${expectedAsin}?language=ja_JP`,
      ...Object.fromEntries(
        safeImages.map((url, index) => [`image_${index + 1}`, url]),
      ),
    },
  };
}
