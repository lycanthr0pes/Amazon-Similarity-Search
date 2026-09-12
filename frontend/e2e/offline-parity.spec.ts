import { expect, test } from "@playwright/test";

test("offline uses production condition groups and requires preparation when enabling images", async ({
  page,
  baseURL,
}) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.origin !== new URL(baseURL!).origin ||
      url.pathname.startsWith("/api")
    ) {
      throw new Error("Offline UI attempted an API or external request");
    }
    await route.continue();
  });
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("合成の入力。白いキーボード。");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "優先条件", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "希望条件", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "否定条件", exact: true }),
  ).toBeVisible();
  await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeEnabled();
});
