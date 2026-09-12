import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 1440, height: 700 } });

test.beforeEach(async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin || url.pathname.startsWith("/api")) {
      await route.abort("blockedbyclient");
      throw new Error(
        "The navigation test attempted an external or API request.",
      );
    }
    await route.continue();
  });
  await page.clock.install();
  await page.goto("/");
  await page.evaluate(() => document.fonts.ready);
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("表示更新を確認する合成入力");
});

test("completed stage circles are blue and returning resets later circles", async ({
  page,
}) => {
  const stages = page
    .getByRole("navigation", { name: "検索の段階" })
    .getByRole("listitem");
  const expectSizes = async (current: number) => {
    const boxes = await stages.evaluateAll((items) =>
      items.map((item) => {
        const ring = item.querySelector("svg")!.getBoundingClientRect();
        const stage = item.getBoundingClientRect();
        return {
          width: ring.width,
          height: ring.height,
          centerY: ring.y + ring.height / 2,
          centerX: ring.x + ring.width / 2,
          stageCenterX: stage.x + stage.width / 2,
        };
      }),
    );
    for (const [index, box] of boxes.entries()) {
      expect(box.width).toBe(index === current ? 44 : 28);
      expect(box.height).toBe(box.width);
      expect(box.centerY).toBe(boxes[current].centerY);
      expect(box.centerX).toBe(box.stageCenterX);
    }
  };
  await expectSizes(0);
  await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1000);
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await expectSizes(1);
  const ring = (index: number) => stages.nth(index).locator("circle");
  await expect(ring(0)).toHaveCSS("fill", "rgb(58, 131, 247)");
  await expect(ring(0)).toHaveCSS("stroke", "rgb(255, 255, 255)");
  await expect(ring(1)).toHaveCSS("fill", "rgb(58, 131, 247)");
  await expect(stages.nth(1)).toHaveAttribute("aria-current", "step");
  await expect(ring(2)).toHaveCSS("fill", "rgb(0, 0, 0)");
  await page.clock.runFor(3500);
  await page.getByRole("button", { name: "条件へ戻る", exact: true }).click();
  await expect(stages.nth(0)).toHaveAttribute("aria-current", "step");
  await expect(ring(1)).toHaveCSS("fill", "rgb(0, 0, 0)");
  await expectSizes(0);
});

test("starting work and asynchronous screen updates preserve scroll while focusing the heading", async ({
  page,
}) => {
  const start = page.getByRole("button", { name: "条件を整理", exact: true });
  await start.focus();
  const before = await page.evaluate(() => window.scrollY);
  expect(before).toBeGreaterThan(0);
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "条件を整理しています", exact: true }),
  ).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(before);
  await page.evaluate(() => window.scrollTo(0, 120));
  await page.clock.runFor(1000);
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(120);
  await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await page.clock.runFor(1500);
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await page.evaluate(() => window.scrollTo(0, 120));
  await page.clock.runFor(3500);
  await expect(
    page.getByRole("heading", { name: "まず1枚、見た目を確認", exact: true }),
  ).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(120);
});

test("history uses shared headings, saved conditions and restores search", async ({
  page,
}) => {
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "検索の段階" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("保存された検索結果はまだありません"),
  ).toBeVisible();
  const historyY = (await page
    .getByRole("heading", { name: "検索履歴", exact: true })
    .boundingBox())!.y;
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1500);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.clock.runFor(15000);
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  const title = page
    .getByRole("list", { name: "検索履歴一覧" })
    .getByRole("heading");
  await expect(title).toHaveCSS("background-color", "rgb(33, 33, 33)");
  await page.getByRole("button", { name: "開く", exact: true }).click();
  const heading = page.getByRole("heading", {
    name: "保存した検索結果",
    exact: true,
  });
  await expect(heading).toBeVisible();
  expect((await heading.boundingBox())!.y).toBe(historyY);
  await expect(
    page.getByRole("navigation", { name: "検索の段階" }),
  ).toHaveCount(0);
  const panel = page.locator("section").filter({
    has: page.getByRole("heading", { name: "確認した条件", exact: true }),
  });
  await expect(panel.locator("dl > div")).toHaveCount(4);
  for (const field of await panel.locator("dd").all()) {
    await expect(field).toHaveCSS("background-color", "rgb(33, 33, 33)");
  }
  await panel.getByRole("button", { name: "削除", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "キャンセル", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "削除", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "履歴へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
});

test("new search stays left of history and is disabled during work", async ({
  page,
}) => {
  const header = page.locator("header");
  const start = header.getByRole("button", { name: "新しく検索", exact: true });
  const other = header.getByRole("button", { name: "検索履歴", exact: true });
  const left = (await start.boundingBox())!;
  const right = (await other.boundingBox())!;
  expect(left.x + left.width).toBeLessThan(right.x);
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(start).toBeDisabled();
  await page.clock.runFor(1500);
  await start.click();
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue("");
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("ヘッダー確認用の合成入力");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1500);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await expect(start).toBeDisabled();
  await page.clock.runFor(15000);
  await expect(start).toBeEnabled();
  await start.click();
  await other.click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
});
