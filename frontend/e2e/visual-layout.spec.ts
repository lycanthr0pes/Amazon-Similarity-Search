import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page, baseURL }) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.origin !== new URL(baseURL!).origin ||
      url.pathname.startsWith("/api")
    ) {
      throw new Error("Visual inspection must remain offline");
    }
    await route.continue();
  });
  await page.clock.install();
  await page.goto("/");
});

test("history shows one storage notice separated from its cards", async ({
  page,
}) => {
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  const notices = page.getByText(/30日間保存します/);
  await expect(notices).toHaveCount(1);
  const notice = await notices.boundingBox();
  const panel = await page.locator("main:visible section").boundingBox();
  expect(panel!.y - notice!.y - notice!.height).toBeGreaterThanOrEqual(24);
});

test("comparison image frames and previews align with wrapping labels", async ({
  page,
}) => {
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("比較画像の目視確認用の合成入力。");
  await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(2500);
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await page.clock.runFor(3500);
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await page.clock.runFor(3500);
  await expect(
    page.getByRole("heading", { name: "比較画像を確認", exact: true }),
  ).toBeVisible();
  const boxes = await page.locator("figure:visible").evaluateAll((figures) =>
    figures.map((figure) => {
      const box = figure.getBoundingClientRect();
      return {
        top: box.top,
        bottom: box.bottom,
        image: figure.querySelector("img")!.getBoundingClientRect().top,
      };
    }),
  );
  expect(boxes).toHaveLength(3);
  for (const key of ["top", "bottom", "image"] as const) {
    expect(
      Math.max(...boxes.map((b) => b[key])) -
        Math.min(...boxes.map((b) => b[key])),
    ).toBeLessThan(1);
  }
});

test("score column headings stay on one line without overflowing the card", async ({
  page,
}) => {
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("採点表の目視確認用の合成入力。");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(2500);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.clock.runFor(15000);
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  const card = page
    .getByRole("list", { name: "検索結果" })
    .getByRole("listitem")
    .first();
  await card.locator("summary").click();
  const sizes = await card.locator("thead th").evaluateAll((cells) =>
    cells.map((cell) => {
      const range = document.createRange();
      range.selectNodeContents(cell);
      return range.getClientRects().length;
    }),
  );
  expect(sizes).toEqual([1, 1, 1, 1]);
  expect(await card.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
});
