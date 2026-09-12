import { expect, test, type Page } from "@playwright/test";

const previewOrigin = "http://127.0.0.1:4173";
const exampleQuery = "操作の継続を確認する合成入力。白いキーボード。";

test.setTimeout(60_000);

test.beforeEach(async ({ page }) => {
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (
      url.origin !== previewOrigin ||
      url.pathname.startsWith("/api") ||
      ["fetch", "xhr"].includes(request.resourceType())
    ) {
      await route.abort("blockedbyclient");
      throw new Error("The offline interaction attempted a non-asset request.");
    }
    await route.continue();
  });
});

async function startResearch(page: Page, scenario = "default") {
  await page.goto(`/?scenario=${scenario}`);
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill(exampleQuery);
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "商品を調査", exact: true }),
  ).toBeVisible();
}

async function showResults(page: Page) {
  const show = page.getByRole("button", { name: "結果を見る", exact: true });
  await expect(show).toBeEnabled({ timeout: 20_000 });
  await show.click();
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
}

test("dismissing the cancellation dialog leaves the running research active", async ({
  page,
}) => {
  await startResearch(page);
  const stop = page.getByRole("button", { name: "検索を中止", exact: true });
  await stop.click();
  const dialog = page.getByRole("dialog", {
    name: "検索を中止しますか？",
    exact: true,
  });
  const cancel = dialog.getByRole("button", {
    name: "キャンセル",
    exact: true,
  });
  await expect(cancel).toBeFocused();
  await cancel.click();
  await expect(dialog).toHaveCount(0);
  await expect(stop).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "商品を調査", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "結果を見る", exact: true }),
  ).toBeDisabled();
  await expect(
    page
      .getByRole("list", { name: "商品調査の進行" })
      .locator('[aria-current="step"]'),
  ).toHaveCount(1);
  await showResults(page);
  await expect(
    page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
  ).toHaveCount(10);
});

test("opening history during research preserves the running search and saves it once", async ({
  page,
}) => {
  await startResearch(page);
  const history = page.getByRole("button", { name: "検索履歴", exact: true });
  await expect(history).toBeEnabled();
  await history.click();
  await expect(
    page.getByRole("heading", { name: "検索履歴", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "商品を調査", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "結果を見る", exact: true }),
  ).toBeDisabled();
  await showResults(page);
  await history.click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
  await expect(page.getByText(exampleQuery, { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "メカニカルキーボード", exact: true }),
  ).toHaveCount(1);
});

test("cancelling discard keeps unsaved results available for a save retry", async ({
  page,
}) => {
  await startResearch(page, "save-error");
  await showResults(page);
  const results = page.getByRole("list", { name: "検索結果" });
  await expect(results.getByRole("listitem")).toHaveCount(10);
  const newSearch = page.getByRole("button", {
    name: "新しく検索",
    exact: true,
  });
  await newSearch.click();
  const dialog = page.getByRole("dialog", {
    name: "保存されていない結果を破棄しますか？",
    exact: true,
  });
  const cancel = dialog.getByRole("button", {
    name: "キャンセル",
    exact: true,
  });
  await expect(cancel).toBeFocused();
  await cancel.click();
  await expect(dialog).toHaveCount(0);
  await expect(newSearch).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
  await expect(results.getByRole("listitem")).toHaveCount(10);
  await page.getByRole("button", { name: "保存を再試行", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "保存を再試行", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
});

test("result conditions expand inside their card while the other candidates remain visible", async ({
  page,
}) => {
  await startResearch(page);
  await showResults(page);
  const results = page.getByRole("list", { name: "検索結果" });
  const cards = results.getByRole("listitem");
  const firstCard = cards.first();
  const secondName = await cards.nth(1).getByRole("heading").textContent();
  const conditions = firstCard
    .locator("summary")
    .filter({ hasText: "検索詳細" });
  await conditions.click();
  await expect(cards).toHaveCount(10);
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(cards.nth(1).getByRole("heading")).toHaveText(secondName!);
  await expect(firstCard.locator("details")).toHaveAttribute("open", "");
  await expect(firstCard).toContainText("一致");
  await expect(
    firstCard.getByRole("table", { name: "点数の内訳" }),
  ).toBeVisible();
  await expect(firstCard).toContainText("画像評価：未使用");
  await conditions.click();
  await expect(firstCard.locator("details")).not.toHaveAttribute("open");
  await expect(
    firstCard.getByRole("button", { name: "詳細", exact: true }),
  ).toHaveCount(0);
  await expect(cards).toHaveCount(10);
});
