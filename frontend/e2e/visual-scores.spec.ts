import { expect, test } from "@playwright/test";

test("mock results and saved history show text-image before image-image scores", async ({
  page,
  baseURL,
}) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.origin !== new URL(baseURL!).origin ||
      url.pathname.startsWith("/api")
    )
      throw new Error("Unexpected external request");
    await route.continue();
  });
  await page.clock.install();
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("合成マグカップ。丸い形。");
  await page.getByRole("switch", { name: /参考画像を使う/ }).press("Space");
  await page
    .getByRole("button", { name: "条件を整理", exact: true })
    .press("Enter");
  await page.clock.runFor(2500);
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .press("Enter");
  await page.clock.runFor(3500);
  await page
    .getByRole("button", { name: "了承して生成", exact: true })
    .press("Enter");
  await page.clock.runFor(3500);
  await page
    .getByRole("button", { name: "最終確認へ", exact: true })
    .press("Enter");
  await page.getByRole("button", { name: "検索", exact: true }).press("Enter");
  await page.clock.runFor(15000);
  await page
    .getByRole("button", { name: "結果を見る", exact: true })
    .press("Enter");
  const first = page
    .getByRole("list", { name: "検索結果" })
    .getByRole("listitem")
    .first();
  await first.getByText("検索詳細", { exact: true }).press("Enter");
  await expect(first).toContainText("文章と画像：95.0");
  await expect(first).toContainText("画像同士：90.0");
  await expect(
    first.getByRole("columnheader", { name: "重み", exact: true }),
  ).toBeVisible();
  await expect(first).toContainText("1倍");
  await expect(first).not.toContainText("参考合成点");
  await expect(
    first.getByText("文章と画像：95.0", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "検索履歴", exact: true })
    .press("Enter");
  await page
    .getByRole("button", { name: "開く", exact: true })
    .first()
    .press("Enter");
  const saved = page
    .getByRole("list", { name: "検索結果" })
    .getByRole("listitem")
    .first();
  await saved.getByText("検索詳細", { exact: true }).press("Enter");
  await expect(saved).toContainText("文章と画像：95.0");
  await expect(saved).toContainText("画像同士：90.0");
  await expect(
    saved.getByRole("columnheader", { name: "重み", exact: true }),
  ).toBeVisible();
  await expect(saved).toContainText("1倍");
});
