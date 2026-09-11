import { expect, test } from "@playwright/test";

for (const reducedMotion of ["no-preference", "reduce"] as const) {
  test(`results return to the top with ${reducedMotion}`, async ({
    page,
    baseURL,
  }) => {
    await page.emulateMedia({ reducedMotion });
    const origin = new URL(baseURL!).origin;
    await page.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== origin || url.pathname.startsWith("/api")) {
        await route.abort("blockedbyclient");
        throw new Error(
          "The top-button test attempted an external or API request.",
        );
      }
      await route.continue();
    });
    await page.clock.install();
    await page.goto("/");
    const top = page.getByRole("button", { name: "トップに戻る", exact: true });
    await expect(top).toHaveCount(0);
    await page
      .getByRole("textbox", { name: "探している商品" })
      .fill("先頭移動を確認する合成入力");
    await page.getByRole("button", { name: "条件を整理", exact: true }).click();
    await page.clock.runFor(1000);
    await page
      .getByRole("button", { name: "画像なしで進む", exact: true })
      .click();
    await page.getByRole("button", { name: "検索", exact: true }).click();
    await page.clock.runFor(15000);
    await page.getByRole("button", { name: "結果を見る", exact: true }).click();
    await expect(top).toBeVisible();
    await expect(top).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await expect(top).toHaveCSS("color", "rgb(0, 0, 0)");
    await expect(top).toHaveCSS("position", "fixed");
    await expect(top.locator("path")).toHaveCSS("stroke", "rgb(0, 0, 0)");
    await expect(top).toHaveCSS("box-shadow", /0px 0px 20px 4px/);
    const initial = (await top.boundingBox())!;
    expect(initial.x + initial.width).toBe(page.viewportSize()!.width - 24);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    expect(await top.boundingBox()).toEqual(initial);
    await top.click();
    await page.clock.runFor(1000);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    await expect(
      page.getByRole("heading", { name: "条件に近い商品", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("list", { name: "検索結果" }).getByRole("listitem"),
    ).toHaveCount(10);
    await page.evaluate(() => window.scrollTo(0, 900));
    await top.focus();
    await page.keyboard.press("Enter");
    await page.clock.runFor(1000);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  });
}
