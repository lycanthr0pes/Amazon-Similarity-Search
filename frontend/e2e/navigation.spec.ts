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
  await page.clock.runFor(2500);
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
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await page.evaluate(() => window.scrollTo(0, 120));
  await page.clock.runFor(2500);
  await expect(
    page.getByRole("heading", { name: "まず1枚、見た目を確認", exact: true }),
  ).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(120);
});

test("history list and details omit the stage space and use shaded titles", async ({
  page,
}) => {
  const positions = () =>
    page.evaluate(() => {
      const heading = document.querySelector("main h1")!;
      const notice = Array.from(document.querySelectorAll("main div")).find(
        (element) =>
          element.textContent?.startsWith(
            "オフラインモック · 入力内容の理解",
          ) && element.children.length === 0,
      )!;
      return [heading, notice].map((element) => {
        const box = element.getBoundingClientRect();
        return { x: box.x, y: box.y + window.scrollY, width: box.width };
      });
    });
  const searchPositions = await positions();
  let historyPositions: Awaited<ReturnType<typeof positions>> | undefined;
  const expectHistoryLayout = async () => {
    const current = await positions();
    expect(current[0].y).toBeLessThan(searchPositions[0].y);
    expect(current[0].width).toBe(searchPositions[0].width);
    if (historyPositions) {
      expect(current).toEqual(historyPositions);
    }
    historyPositions = current;
    await expect(
      page.getByRole("navigation", { name: "検索の段階", includeHidden: true }),
    ).toHaveCount(0);
  };
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expectHistoryLayout();
  await expect(page.getByText("検索履歴はまだありません")).toBeVisible();
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1000);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.clock.runFor(15000);
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expectHistoryLayout();
  const title = page
    .getByRole("list", { name: "検索履歴一覧" })
    .getByRole("heading")
    .first();
  await expect(title).toHaveCSS("background-color", "rgb(33, 33, 33)");
  await expect(title).toHaveCSS("color", "rgb(255, 255, 255)");
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expectHistoryLayout();
  const panel = page.locator("section").filter({
    has: page.getByRole("heading", { name: "確認した条件", exact: true }),
  });
  const fields = panel.locator("dl > div");
  await expect(fields).toHaveCount(5);
  const first = (await fields.nth(0).boundingBox())!;
  const second = (await fields.nth(1).boundingBox())!;
  const third = (await fields.nth(2).boundingBox())!;
  expect(first.y).toBe(second.y);
  expect(second.x).toBeGreaterThan(first.x);
  expect(third.x).toBe(first.x);
  expect(third.y).toBeGreaterThan(first.y);
  for (const field of await fields.all()) {
    await expect(field.locator("dd")).toHaveCSS(
      "background-color",
      "rgb(33, 33, 33)",
    );
    await expect(field.locator("dd")).toHaveCSS("border-radius", "15px");
    await expect(field.locator("dt")).toHaveCSS(
      "background-color",
      "rgba(0, 0, 0, 0)",
    );
  }
  const actions = panel.locator(":scope > :last-child");
  const remove = actions.getByRole("button", { name: "削除", exact: true });
  const back = actions.getByRole("button", { name: "履歴へ戻る", exact: true });
  await expect(remove).toBeVisible();
  await expect(back).toBeVisible();
  const left = (await remove.boundingBox())!;
  const right = (await back.boundingBox())!;
  expect(left.y).toBe(right.y);
  expect(left.x).toBeLessThan(right.x);
  await remove.click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "キャンセル", exact: true })
    .click();
  await expect(remove).toBeFocused();

  await page.getByRole("button", { name: "履歴へ戻る", exact: true }).click();
  await expectHistoryLayout();
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "検索の段階" }),
  ).toBeVisible();
});

test("new search stays left of history and resets pending mock work", async ({
  page,
}) => {
  const header = page.locator("header");
  const start = header.getByRole("button", { name: "新しく検索", exact: true });
  const expectHeader = async () => {
    await expect(start).toBeVisible();
    const other = header.getByRole("button", {
      name: /^(検索履歴|検索へ戻る)$/,
    });
    const left = (await start.boundingBox())!;
    const right = (await other.boundingBox())!;
    expect(left.y).toBe(right.y);
    expect(left.x + left.width).toBeLessThan(right.x);
    await expect(
      page.getByRole("button", { name: "新しく検索", exact: true }),
    ).toHaveCount(1);
  };
  await expectHeader();
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expectHeader();
  await start.click();
  await page.clock.runFor(2000);
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue("");
  await header.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expectHeader();
  await start.click();
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("ヘッダー確認用の合成入力");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1000);
  await expectHeader();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expectHeader();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await expectHeader();
  await start.click();
  await page.clock.runFor(15000);
  await expect(
    page.getByRole("textbox", { name: "探している商品" }),
  ).toHaveValue("");
  await header.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(page.getByText("検索履歴はまだありません")).toBeVisible();
});
