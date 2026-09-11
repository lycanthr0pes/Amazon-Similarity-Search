import { expect, test, type Locator } from "@playwright/test";

const INPUT = "表示確認用の合成入力。白いキーボード。";

test.beforeEach(async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin || url.pathname.startsWith("/api")) {
      await route.abort("blockedbyclient");
      throw new Error("The control test attempted an external or API request.");
    }
    await route.continue();
  });
});

test("primary button text stays legible while disabled, hovered, and organizing", async ({
  page,
}) => {
  await page.goto("/");
  await expect
    .soft(page.getByText("希望を確かめながら、ひとつずつ。", { exact: true }))
    .toHaveCount(0);
  await expect
    .soft(
      page.getByRole("heading", { name: "希望から、比較へ。", exact: true }),
    )
    .toHaveCount(0);
  await expect.soft(page.getByText(/01　条件を確かめる/)).toHaveCount(0);
  await expect(
    page.getByText(/オフラインモック · 入力内容の理解/),
  ).toBeVisible();
  await expect(page.locator("#query-help")).toContainText(
    "同じキーボードのデモ条件",
  );
  const input = page.getByRole("textbox", { name: "探している商品" });
  await expect.soft(input).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(input).toHaveCSS("background-color", "rgb(33, 33, 33)");
  const placeholder = await input.evaluate(
    (element) => getComputedStyle(element, "::placeholder").color,
  );
  expect.soft(placeholder).toBe("rgb(160, 160, 160)");
  const description = await page.locator('label[for="query"]').boundingBox();
  const inputBox = await input.boundingBox();
  expect.soft(inputBox!.y - description!.y - description!.height).toBe(16);
  const primary = page.getByRole("button", { name: "条件を整理", exact: true });
  const history = page.getByRole("button", { name: "検索履歴", exact: true });
  await expect(primary).toHaveCSS(
    "box-shadow",
    "rgb(255, 255, 255) 0px 0px 0px 1px inset, rgb(255, 255, 255) 0px 0px 0px 1px inset",
  );
  await expect(history).toHaveCSS(
    "box-shadow",
    "rgb(255, 255, 255) 0px 0px 0px 1px inset, rgb(255, 255, 255) 0px 0px 0px 1px inset",
  );
  await expect(primary).toBeDisabled();
  await expect(primary).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(primary).toHaveCSS("color", "rgb(0, 0, 0)");
  await expect(primary).toHaveCSS("font-weight", "500");

  await page.getByRole("textbox", { name: "探している商品" }).fill(INPUT);
  await expect(primary).toBeEnabled();
  await expect(primary).toHaveCSS("color", "rgb(0, 0, 0)");
  await primary.hover();
  await expect(primary).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(primary).toHaveCSS("color", "rgb(255, 255, 255)");
  await page.mouse.move(0, 0);
  await expect(primary).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(primary).toHaveCSS("color", "rgb(0, 0, 0)");

  await primary.click();
  const busy = page.getByRole("button", { name: "整理中", exact: true });
  await expect(busy).toBeDisabled();
  await expect(busy).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(busy).toHaveCSS("color", "rgb(0, 0, 0)");
  await expect(busy.locator('span[aria-hidden="true"]')).toHaveCSS(
    "color",
    "rgb(0, 0, 0)",
  );
});

test("reference-image switch supports pointer and keyboard and retains its choice", async ({
  page,
}) => {
  await page.goto("/");
  const toggle = page.getByRole("switch", { name: /参考画像を使う/ });
  const track = page.getByTestId("toggle-track");
  const thumb = page.getByTestId("toggle-thumb");
  await expect(toggle).not.toBeChecked();
  await expect(track).toHaveCSS("background-color", "rgb(66, 66, 66)");
  await expect
    .poll(() =>
      thumb.evaluate((element) => {
        const circle = element.querySelector("circle");
        return circle
          ? getComputedStyle(circle).fill
          : getComputedStyle(element).backgroundColor;
      }),
    )
    .toBe("rgb(255, 255, 255)");
  const off = await thumb.boundingBox();
  expect(off).not.toBeNull();

  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(track).toHaveCSS("background-color", "rgb(58, 131, 247)");
  await expect(thumb).toHaveCSS("transform", "matrix(1, 0, 0, 1, 24, 0)");
  const on = await thumb.boundingBox();
  expect(on!.x - off!.x).toBe(24);
  expect(on!.width).toBe(on!.height);
  await toggle.focus();
  await page.keyboard.press("Space");
  await expect(toggle).not.toBeChecked();
  await expect(track).toHaveCSS("background-color", "rgb(66, 66, 66)");
  await page.keyboard.press("Space");
  await expect(toggle).toBeChecked();

  await page.getByRole("textbox", { name: "探している商品" }).fill(INPUT);
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(toggle).toBeDisabled();
  await expect(toggle).toBeChecked();
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
  await expect(toggle).toBeEnabled();
  await expect(toggle).toBeChecked();
  await expect(track).toHaveCSS("background-color", "rgb(58, 131, 247)");
  await toggle.uncheck();
  await expect(
    page.getByRole("button", { name: "画像なしで進む", exact: true }),
  ).toBeEnabled();
});

async function expectUnclippedRing(svg: Locator) {
  const bounds = await svg.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.width).toBe(bounds!.height);
  const ring = svg.locator("circle").first();
  await expect(ring).toHaveCount(1);
  await expect(ring).toHaveCSS("stroke", "rgb(255, 255, 255)");
  const geometry = await ring.evaluate((element) => {
    const circle = element as SVGCircleElement;
    const box = circle.getBBox();
    const view = circle.ownerSVGElement!.viewBox.baseVal;
    const halfStroke =
      Number.parseFloat(getComputedStyle(circle).strokeWidth) / 2;
    return {
      left: box.x - halfStroke - view.x,
      top: box.y - halfStroke - view.y,
      right: view.x + view.width - box.x - box.width - halfStroke,
      bottom: view.y + view.height - box.y - box.height - halfStroke,
    };
  });
  for (const margin of Object.values(geometry)) {
    expect(margin).toBeGreaterThanOrEqual(0);
  }
}

for (const deviceScaleFactor of [1, 2]) {
  test.describe(`circle rendering at DPR ${deviceScaleFactor}`, () => {
    test.use({ deviceScaleFactor });

    test("progress and research rings remain square with an unclipped white stroke", async ({
      page,
    }, testInfo) => {
      await page.goto("/");
      await page.evaluate(() => document.fonts.ready);
      const stages = page.getByRole("navigation", { name: "検索の段階" });
      const rings = stages.getByTestId("progress-ring");
      await expect(rings).toHaveCount(5);
      for (const ring of await rings.all()) {
        await expectUnclippedRing(ring);
      }
      await stages.screenshot({
        path: testInfo.outputPath("progress-rings.png"),
      });

      await page.getByRole("textbox", { name: "探している商品" }).fill(INPUT);
      await page
        .getByRole("button", { name: "条件を整理", exact: true })
        .click();
      await page
        .getByRole("button", { name: "画像なしで進む", exact: true })
        .click();
      await page.getByRole("button", { name: "検索", exact: true }).click();
      const research = page.getByRole("list", { name: "商品調査の進行" });
      const researchRings = research.locator("svg");
      await expect(researchRings).toHaveCount(5);
      for (const ring of await researchRings.all()) {
        await expectUnclippedRing(ring);
      }
      await research.screenshot({
        path: testInfo.outputPath("research-rings.png"),
      });
    });
  });
}
