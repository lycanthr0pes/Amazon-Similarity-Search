import { expect, test, type Page } from "@playwright/test";

const INPUT = "復帰動作を確認するための合成入力。白いキーボード。";
test.beforeEach(async ({ page, baseURL }) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.origin !== new URL(baseURL!).origin ||
      url.pathname.startsWith("/api") ||
      ["fetch", "xhr"].includes(route.request().resourceType())
    ) {
      throw new Error("Offline recovery attempted a non-asset request");
    }
    await route.continue();
  });
  await page.clock.install();
});
async function organize(page: Page, scenario = "default", images = false) {
  await page.goto(`/?scenario=${scenario}`);
  await page.getByRole("textbox", { name: "探している商品" }).fill(INPUT);
  if (images) {
    await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  }
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1500);
}
async function finalReview(page: Page, scenario = "default") {
  await organize(page, scenario);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
}
async function firstImage(page: Page, scenario = "default") {
  await organize(page, scenario, true);
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await page.clock.runFor(3500);
}
async function finish(page: Page) {
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.clock.runFor(15000);
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
}
async function regenerate(page: Page) {
  await page.getByRole("button", { name: "作り直す", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "作り直す", exact: true })
    .click();
  await page.clock.runFor(3500);
}

test("organization failure preserves input for explicit correction or retry", async ({
  page,
}) => {
  await organize(page, "organize-error");
  await expect(page.getByRole("alert")).toContainText("条件を整理できません");
  await page.getByRole("button", { name: "条件へ戻る", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue(INPUT);
  await page.getByRole("button", { name: "修正をやめる", exact: true }).click();
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await page.clock.runFor(1500);
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
});

test("failed image consumes an attempt and cancelling regeneration consumes none", async ({
  page,
}) => {
  await firstImage(page, "reference-error");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("作り直せる回数：残り1回", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "作り直す", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "キャンセル", exact: true })
    .click();
  await expect(
    page.getByText("作り直せる回数：残り1回", { exact: true }),
  ).toBeVisible();
  await regenerate(page);
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "作り直す", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
});

test("failed comparison cannot be adopted and fresh reference needs approval", async ({
  page,
}) => {
  await firstImage(page, "comparison-error");
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await page.clock.runFor(3500);
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toHaveCount(0);
  await regenerate(page);
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await page.clock.runFor(3500);
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
});

test("research failure stores no history and recovery repeats final confirmation", async ({
  page,
}) => {
  await finalReview(page, "research-error");
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.clock.runFor(2500);
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await page.clock.runFor(1500);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await finish(page);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
});

test("save-only retry stores one snapshot across reload", async ({ page }) => {
  await finalReview(page, "save-error");
  await finish(page);
  await expect(page.getByRole("alert")).toContainText(
    "結果を履歴に保存できませんでした",
  );
  await page.getByRole("button", { name: "保存を再試行", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "保存を再試行", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue("");
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(page.getByText(INPUT, { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "表示件数" }).selectOption("30");
  await expect(
    page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
  ).toHaveCount(12);
});

test("delete failure keeps the history card until explicit retry", async ({
  page,
}) => {
  await finalReview(page, "delete-error");
  await finish(page);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await page.getByRole("button", { name: "削除", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "削除", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "履歴を削除できませんでした",
  );
  const rows = page
    .getByRole("list", { name: "検索履歴一覧" })
    .getByRole("listitem");
  await expect(rows).toHaveCount(1);
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await expect(rows).toHaveCount(0);
});

test("empty results can be reopened without another search", async ({
  page,
}) => {
  await finalReview(page, "empty");
  await finish(page);
  await expect(
    page.getByRole("heading", {
      name: "条件に合う商品がありません",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "条件に合う商品がありません",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toHaveCount(0);
});

test("expired reference confirmation allows image-free recovery", async ({
  page,
}) => {
  await firstImage(page);
  await page.clock.fastForward(15 * 60_000 + 2000);
  await expect(page.getByRole("alert")).toContainText("期限");
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
});

test("expired image-free final requires new preparation and confirmation", async ({
  page,
}) => {
  await finalReview(page);
  await page.clock.fastForward(15 * 60_000 + 2000);
  await expect(page.getByRole("alert")).toContainText("期限");
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "条件へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await page.clock.runFor(1500);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
});

test("returning to natural language editing invalidates images after applying", async ({
  page,
}) => {
  await firstImage(page);
  await page.getByRole("button", { name: "条件へ戻る", exact: true }).click();
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("合成商品。持ち運べること。");
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await page.clock.runFor(1500);
  await expect(
    page.getByRole("textbox", { name: "優先条件", exact: true }),
  ).toHaveValue("持ち運べること");
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("switch", { name: /参考画像を使う/ }).uncheck();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(page.getByText("持ち運べること", { exact: true })).toBeVisible();
});

test("edited comparison prompts reuse reference and consume remaining set", async ({
  page,
}) => {
  await firstImage(page);
  await page
    .getByRole("textbox", { name: "比較画像のプロンプト：色", exact: true })
    .fill("Change only the color.");
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await page.clock.runFor(3500);
  await page
    .getByRole("textbox", { name: "比較画像のプロンプト：色", exact: true })
    .fill("Second color instruction.");
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "比較画像を再生成", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "作り直す", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "比較画像を準備", exact: true }),
  ).toBeVisible();
  await page.clock.runFor(3500);
  await expect(
    page.getByText("作り直せる回数：残り0回", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await expect(page.getByTestId("final-product-name")).toHaveText(
    "メカニカルキーボード",
  );
});
