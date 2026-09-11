import { expect, test } from "@playwright/test";

test("result cards show ranked badges, concise conditions, and zoomable images", async ({
  page,
  baseURL,
}, testInfo) => {
  const origin = new URL(baseURL!).origin;
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin || url.pathname.startsWith("/api")) {
      await route.abort("blockedbyclient");
      throw new Error("The results test attempted an external or API request.");
    }
    await route.continue();
  });
  await page.clock.install();
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill("結果表示用の合成入力");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page.clock.runFor(1000);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await page.getByRole("button", { name: "検索", exact: true }).click();
  await page.clock.runFor(15000);
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await page.getByRole("combobox", { name: "表示件数" }).selectOption("12");
  const cards = page
    .getByRole("list", { name: "検索結果" })
    .getByRole("listitem");
  await expect(cards).toHaveCount(12);
  const first = cards.first();
  const matching = first.locator("summary").filter({ hasText: "検索条件" });
  await expect(matching).toBeVisible();
  await expect(first.getByText("未確認：静音性", { exact: true })).toBeHidden();
  await matching.click();
  await expect(
    first.getByText("未確認：静音性", { exact: true }),
  ).toBeVisible();
  await matching.focus();
  await page.keyboard.press("Enter");
  await expect(first.getByText("未確認：静音性", { exact: true })).toBeHidden();
  await page.keyboard.press("Space");
  for (const index of [1, 11]) {
    await cards
      .nth(index)
      .locator("summary")
      .filter({ hasText: "検索条件" })
      .click();
  }
  await expect(
    cards.nth(2).getByText("未確認：接続可能な機器", { exact: true }),
  ).toBeHidden();

  await expect
    .soft(first.getByText("未確認：静音性", { exact: true }))
    .toBeVisible();
  await expect
    .soft(cards.nth(1).getByText("未確認：接続可能な機器", { exact: true }))
    .toBeVisible();
  await expect
    .soft(
      cards.last().getByText("不一致：テンキー・本体サイズ", { exact: true }),
    )
    .toBeVisible();
  await expect
    .soft(cards.getByText(/確認できない：|合わない：|は未確認/))
    .toHaveCount(0);
  for (const index of [0, 11]) {
    const card = cards.nth(index);
    const rank = card.getByText(`#${index + 1}`, { exact: true });
    await expect(rank).toHaveCSS("background-color", "rgb(58, 131, 247)");
    await expect(rank).toHaveCSS("border-top-left-radius", "15px");
    await expect(rank).toHaveCSS("border-top-right-radius", "0px");
    await expect(rank).toHaveCSS("border-bottom-left-radius", "0px");
    await expect(rank).toHaveCSS("border-bottom-right-radius", "15px");
    const cardBox = (await card.boundingBox())!;
    const rankBox = (await rank.boundingBox())!;
    expect(rankBox.x).toBe(cardBox.x);
    expect(rankBox.y).toBe(cardBox.y);
    await expect(
      card.getByRole("button", { name: "詳細", exact: true }),
    ).toHaveCount(0);
    await expect(card.getByRole("heading").getByRole("link")).toHaveCount(0);
  }
  const name = await first.getByRole("heading").innerText();
  const zoom = first.getByRole("button", {
    name: `${name}を拡大`,
    exact: true,
  });
  await zoom.hover();
  await expect(zoom.getByTestId("zoom-icon")).toHaveCSS("opacity", "1");
  await first.screenshot({ path: testInfo.outputPath("result-card.png") });
  await zoom.getByRole("img").click();
  const dialog = page.getByRole("dialog", { name, exact: true });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("img")).toHaveAttribute(
    "src",
    (await zoom.getByRole("img").getAttribute("src"))!,
  );
  await page.keyboard.press("Escape");
  await expect(zoom).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "閉じる", exact: true }).click();
  await expect(
    first.getByRole("button", { name: "詳細", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await page.getByRole("button", { name: "開く", exact: true }).click();
  const savedZoom = page.getByRole("button", {
    name: `${name}を拡大`,
    exact: true,
  });
  await savedZoom.click();
  await expect(dialog).toBeVisible();
});
