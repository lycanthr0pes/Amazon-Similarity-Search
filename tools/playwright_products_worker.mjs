import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import { collect } from "./playwright_products_collect.mjs";

const PAGE_TIMEOUT_MS = 30000;
const MAX_INPUT_BYTES = 16000;
const MAX_OUTPUT_BYTES = 8 * 1024 * 1024;
const MAX_RESOURCE_REQUESTS = 200;

function emit(event) {
  const line = JSON.stringify(event);
  if (Buffer.byteLength(line) > MAX_OUTPUT_BYTES) {
    throw new Error("response_limit");
  }
  process.stdout.write(line + "\n");
}

function permittedHost(host) {
  return ["amazon.co.jp", "media-amazon.com", "ssl-images-amazon.com"].some(
    (root) => host === root || host.endsWith("." + root),
  );
}

async function openPage(context, target, metrics) {
  const page = await context.newPage();
  let allowed = 0;
  let mainRequests = 0;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const main =
      request.isNavigationRequest() && request.frame() === page.mainFrame();
    if (main) {
      mainRequests++;
    }
    const permitted =
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      !url.port &&
      permittedHost(url.hostname) &&
      ["GET", "HEAD"].includes(request.method()) &&
      allowed < MAX_RESOURCE_REQUESTS &&
      (main
        ? request.url() === target && mainRequests === 1
        : !request.isNavigationRequest() &&
          !["image", "font", "media"].includes(request.resourceType()));
    if (permitted) {
      allowed++;
      metrics.requests_allowed++;
      await route.continue();
    } else {
      metrics.requests_blocked++;
      await route.abort();
    }
  });
  try {
    const response = await page.goto(target, {
      waitUntil: "domcontentloaded",
      timeout: PAGE_TIMEOUT_MS,
    });
    if (!response || response.status() !== 200 || page.url() !== target) {
      throw new Error("page_unavailable");
    }
    return page;
  } catch (error) {
    await page.close();
    throw error;
  }
}

let browser;
try {
  let buffer = "";
  for await (const chunk of process.stdin) {
    buffer += chunk;
    if (Buffer.byteLength(buffer) > MAX_INPUT_BYTES) {
      throw new Error("input_limit");
    }
  }
  const input = JSON.parse(buffer);
  if (
    ![
      "limit,queries",
      "englishTitles,limit,queries",
      "englishDetails,englishTitles,limit,queries",
    ].includes(Object.keys(input).sort().join(",")) ||
    (Object.hasOwn(input, "englishTitles") && input.englishTitles !== true) ||
    (Object.hasOwn(input, "englishDetails") && input.englishDetails !== true) ||
    !Array.isArray(input.queries) ||
    input.queries.length < 1 ||
    input.queries.length > 2 ||
    input.queries.some(
      (q) =>
        typeof q !== "string" ||
        !q.trim() ||
        q !== q.trim() ||
        q.length > 200 ||
        /[\x00-\x1f\x7f]/.test(q),
    ) ||
    !Number.isInteger(input.limit) ||
    input.limit < 1 ||
    input.limit > 100
  ) {
    throw new Error("input_contract");
  }
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    locale: "ja-JP",
    serviceWorkers: "block",
    acceptDownloads: false,
  });
  emit({ event: "progress" });
  const englishContext = input.englishTitles
    ? await browser.newContext({
        locale: "en-US",
        serviceWorkers: "block",
        acceptDownloads: false,
      })
    : null;
  const result = await collect(
    context,
    englishContext,
    input,
    {
      search_pages: 0,
      detail_pages: 0,
      ...(input.englishTitles ? { english_detail_pages: 0 } : {}),
      requests_allowed: 0,
      requests_blocked: 0,
    },
    { openPage, emit },
  );
  if (englishContext) await englishContext.close();
  await context.close();
  await browser.close();
  browser = null;
  emit({ event: "result", result });
} catch (error) {
  const codes = new Set([
    "input_limit",
    "input_contract",
    "response_limit",
    "page_unavailable",
    "challenge",
    "search_contract",
    "product_contract",
  ]);
  emit({
    event: "error",
    code: codes.has(error.message) ? error.message : "browser_failure",
  });
  process.exitCode = 1;
} finally {
  if (browser) {
    await browser.close();
  }
}
