import { expect, test, type Page } from "@playwright/test";

const PREVIEW_ORIGIN = "http://127.0.0.1:4173";
const INPUT = "復帰動作を確認するための合成入力。白いキーボード。";

test.setTimeout(60_000);

test.beforeEach(async ({ page }) => {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (
      url.origin !== PREVIEW_ORIGIN ||
      url.pathname.startsWith("/api") ||
      ["fetch", "xhr"].includes(request.resourceType())
    ) {
      await route.abort("blockedbyclient");
      throw new Error(
        "The offline recovery flow attempted a non-asset request.",
      );
    }
    await route.continue();
  });
});

async function organize(page: Page, scenario = "default") {
  await page.goto(`/?scenario=${scenario}`);
  await page.getByRole("textbox", { name: "探している商品" }).fill(INPUT);
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
}

async function review(page: Page, scenario = "default") {
  await organize(page, scenario);
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
}

async function finalReview(page: Page, scenario = "default") {
  await review(page, scenario);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
}

async function firstImage(page: Page, scenario = "default") {
  await review(page, scenario);
  await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "まず1枚、見た目を確認", exact: true }),
  ).toBeVisible({ timeout: 15_000 });
}

async function showResults(page: Page) {
  const show = page.getByRole("button", { name: "結果を見る", exact: true });
  await expect(show).toBeEnabled({ timeout: 20_000 });
  await show.click();
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
}

test("condition organization failure preserves the input and requires an explicit retry", async ({
  page,
}) => {
  await organize(page, "organize-error");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue(INPUT);
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(INPUT, { exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("failed first image consumes one attempt, while cancelling regeneration consumes none", async ({
  page,
}) => {
  await firstImage(page, "reference-error");
  const approve = page.getByRole("button", {
    name: "了承して生成",
    exact: true,
  });
  await expect(approve).toBeDisabled();
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(
    page.getByText("作り直せる回数：残り1回", { exact: true }),
  ).toBeVisible();
  const regenerate = page.getByRole("button", {
    name: "作り直す",
    exact: true,
  });
  await regenerate.click();
  const dialog = page.getByRole("dialog", {
    name: "参考画像を作り直す",
    exact: true,
  });
  await dialog.getByRole("button", { name: "キャンセル", exact: true }).click();
  await expect(
    page.getByText("作り直せる回数：残り1回", { exact: true }),
  ).toBeVisible();
  await expect(approve).toBeDisabled();
  await regenerate.click();
  await dialog.getByRole("button", { name: "作り直す", exact: true }).click();
  await expect(approve).toBeEnabled({ timeout: 15_000 });
  await expect(
    page.getByText("作り直せる回数：残り0回", { exact: true }),
  ).toBeVisible();
  await expect(regenerate).toBeDisabled();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(page.getByText("参考画像：なし", { exact: true })).toBeVisible();
});

test("failed comparison images cannot be adopted and recovery needs a fresh reference approval", async ({
  page,
}) => {
  await firstImage(page, "comparison-error");
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "比較画像を確認", exact: true }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeDisabled();
  await expect(page.getByTestId("generation-wave")).toHaveCount(0);
  await page.getByRole("button", { name: "作り直す", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "作り直す", exact: true })
    .click();
  const approve = page.getByRole("button", {
    name: "了承して生成",
    exact: true,
  });
  await expect(approve).toBeEnabled({ timeout: 15_000 });
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toHaveCount(0);
  await approve.click();
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeEnabled({ timeout: 15_000 });
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
});

test("research failure returns to confirmation without creating history, then explicit retry completes once", async ({
  page,
}) => {
  await finalReview(page, "research-error");
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "再試行", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await showResults(page);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
});

test("history save failure preserves results and a retry stores one snapshot across reload", async ({
  page,
}) => {
  await finalReview(page, "save-error");
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await showResults(page);
  await expect(
    page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
  ).toHaveCount(10);
  await expect(
    page.getByText(/結果を履歴に保存できませんでした/),
  ).toBeVisible();
  await page.getByRole("button", { name: "保存を再試行", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "保存を再試行", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
  ).toHaveCount(10);
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue("");
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
  await expect(page.getByText(INPUT, { exact: true })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "検索の段階" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
  ).toHaveCount(10);
  await page.getByRole("combobox", { name: "表示件数" }).selectOption("30");
  await expect(
    page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
  ).toHaveCount(12);
});

test("history deletion failure keeps the card until the explicit retry succeeds", async ({
  page,
}) => {
  await finalReview(page, "delete-error");
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await showResults(page);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  const items = page
    .getByRole("list", { name: "検索履歴一覧" })
    .getByRole("listitem");
  await page.getByRole("button", { name: "削除", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "履歴を削除", exact: true });
  await dialog.getByRole("button", { name: "削除", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "履歴を削除できませんでした",
  );
  await dialog.getByRole("button", { name: "キャンセル", exact: true }).click();
  await expect(items).toHaveCount(1);
  await expect(page.getByText(INPUT, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "削除", exact: true }).click();
  await dialog.getByRole("button", { name: "削除", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(items).toHaveCount(0);
});

test("a normal empty result is saved and can be reopened without a new search", async ({
  page,
}) => {
  await finalReview(page, "empty");
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await showResults(page);
  await expect(
    page.getByText(/これは0件の結果を確認するためのモック/),
  ).toBeVisible();
  await expect(page.getByRole("list", { name: "検索結果" })).toHaveCount(0);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByText(/これは0件の結果を確認するためのモック/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toHaveCount(0);
});

test("reference approval expires after fifteen minutes and image-free progress remains available", async ({
  page,
}) => {
  await page.clock.install();
  await firstImage(page);
  await page.clock.fastForward(15 * 60_000 + 1_000);
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toBeDisabled();
  await expect(page.getByRole("alert").first()).toContainText("期限");
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
});

test("expired final confirmation requires a fresh review before search is enabled", async ({
  page,
}) => {
  await page.clock.install();
  await finalReview(page);
  await page.clock.fastForward(15 * 60_000 + 1_000);
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "内容を再確認", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("heading", { name: "商品を調査", exact: true }),
  ).toHaveCount(0);
});

test("returning to edit conditions invalidates the images and requires applying the changes", async ({
  page,
}) => {
  await firstImage(page);
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeEnabled({ timeout: 15_000 });
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await page.getByRole("button", { name: "条件へ戻る", exact: true }).click();
  await page
    .getByRole("textbox", { name: "必ずほしい", exact: true })
    .fill("持ち運べること");
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeEnabled();
  await page.getByRole("switch", { name: /参考画像を使う/ }).uncheck();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(page.getByText("持ち運べること", { exact: true })).toBeVisible();
  await expect(page.getByText("参考画像：なし", { exact: true })).toBeVisible();
});
