import { expect, test, type Page } from "@playwright/test";

const previewOrigin = "http://127.0.0.1:4173";
const exampleQuery = "机で使う、持ち手のある白いマグカップを探しています。";

test.setTimeout(60_000);

test.beforeEach(async ({ page }) => {
  await page.route("**/*", async (route) => {
    const request = new URL(route.request().url());
    const type = route.request().resourceType();
    if (
      request.origin !== previewOrigin ||
      request.pathname.startsWith("/api") ||
      type === "fetch" ||
      type === "xhr"
    ) {
      await route.abort("blockedbyclient");
      throw new Error(
        `Unexpected non-asset request: ${request.origin}${request.pathname}`,
      );
    }
    await route.continue();
  });
});

async function reviewConditions(page: Page) {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "探している商品" })
    .fill(exampleQuery);
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(exampleQuery, { exact: true })).toBeVisible();
}

async function completeSearch(page: Page) {
  const search = page.getByRole("button", { name: "検索", exact: true });
  await expect(search).toBeEnabled();
  await expect(
    page.getByRole("heading", { name: "商品を調査", exact: true }),
  ).toHaveCount(0);
  // Two DOM clicks in the same task exercise the synchronous duplicate-operation guard.
  await search.evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });
  await expect(
    page.getByRole("heading", { name: "商品を調査", exact: true }),
  ).toBeVisible();
  const progress = page.getByRole("list", { name: "商品調査の進行" });
  await expect(progress.getByRole("listitem")).toHaveCount(5);
  await expect(progress.locator('[aria-current="step"]')).toHaveCSS(
    "background-color",
    "rgb(66, 66, 66)",
  );
  await expect(page.getByTestId("research-pulse")).toHaveCSS(
    "animation-duration",
    "1.5s",
  );
  await expect(page.getByTestId("research-pulse")).toHaveCSS(
    "background-color",
    "rgb(58, 131, 247)",
  );
  await expect(
    page.getByRole("button", { name: "結果を見る", exact: true }),
  ).toBeDisabled();
  await expect(progress.getByText("完了", { exact: true })).toHaveCount(5, {
    timeout: 20_000,
  });
  await expect(page.getByTestId("research-pulse")).toHaveCount(0);
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
}

test("input limits and common visual rules are applied in the browser", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("/");
  const heading = page.getByRole("heading", {
    name: "探しているものを、言葉で。",
    exact: true,
  });
  const input = page.getByRole("textbox", { name: "探している商品" });
  const submit = page.getByRole("button", { name: "条件を整理", exact: true });
  const history = page.getByRole("button", { name: "検索履歴", exact: true });
  await expect(heading).toBeVisible();
  await expect(submit).toBeDisabled();
  await input.fill("あ".repeat(2001));
  await expect(submit).toBeDisabled();
  await expect(
    page.getByText("2,000文字以内で入力してください", { exact: true }),
  ).toBeVisible();
  await input.fill("あ".repeat(2000));
  await expect(submit).toBeEnabled();

  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(0, 0, 0)",
  );
  await expect(page.locator("body")).toHaveCSS("color", "rgb(255, 255, 255)");
  await expect(page.locator("body")).toHaveCSS("font-size", "16px");
  await expect(page.locator("body")).toHaveCSS("font-family", /Noto Sans JP/);
  await expect(heading).toHaveCSS("font-size", "40px");
  for (const button of [submit, history]) {
    await expect(button).toHaveCSS("width", "176px");
    await expect(button).toHaveCSS("height", "48px");
    await expect(button).toHaveCSS("border-radius", "100px");
    await expect(button).toHaveCSS("text-align", "center");
  }
  await expect(submit).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(submit).toHaveCSS("color", "rgb(0, 0, 0)");
  await submit.hover();
  await expect(submit).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(submit).toHaveCSS("color", "rgb(255, 255, 255)");
  await history.hover();
  await expect(history).toHaveCSS("background-color", "rgb(66, 66, 66)");
  const currentStep = page
    .getByRole("navigation", { name: "検索の段階" })
    .locator('[aria-current="step"]');
  await expect(currentStep).toHaveCount(1);
  await expect(currentStep).toContainText("条件");
  expect(requests.some((url) => new URL(url).pathname.endsWith(".woff2"))).toBe(
    true,
  );
});

test("the image-free flow preserves input, renders fixed results, and records one search", async ({
  page,
}, testInfo) => {
  await reviewConditions(page);
  await expect(
    page.getByRole("switch", { name: /参考画像を使う/ }),
  ).not.toBeChecked();
  await expect(page.getByText(/固定の合成/).first()).toBeVisible();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
  await completeSearch(page);

  const results = page.getByRole("list", { name: "検索結果" });
  await expect(results.getByRole("listitem")).toHaveCount(10);
  const count = page.getByRole("combobox", { name: "表示件数" });
  await count.selectOption("3");
  await expect(results.getByRole("listitem")).toHaveCount(3);
  await count.selectOption("30");
  expect(await results.getByRole("listitem").count()).toBeGreaterThan(10);
  expect(await results.getByRole("listitem").count()).toBeLessThanOrEqual(30);
  await page.screenshot({
    path: testInfo.outputPath("results.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "検索履歴", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(exampleQuery, { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "メカニカルキーボード", exact: true }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "条件に近い商品", exact: true }),
  ).toBeVisible();
});

test("reference and comparison images require separate explicit approval before search", async ({
  page,
}, testInfo) => {
  await reviewConditions(page);
  await page.getByRole("switch", { name: /参考画像を使う/ }).check();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("heading", { name: "まず1枚、見た目を確認", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await expect(page.getByText(/^生成中\.*$/).first()).toBeVisible();
  const pop = page.getByLabel("生成中", { exact: true }).first().locator("..");
  const popBox = (await pop.boundingBox())!;
  expect.soft(popBox.width).toBe(96);
  expect.soft(popBox.height).toBe(32);
  await expect(page.getByTestId("generation-wave")).toHaveCSS(
    "animation-duration",
    "1.5s",
  );
  await expect(page.getByTestId("generation-wave")).toHaveCSS(
    "animation-iteration-count",
    "infinite",
  );
  const approve = page.getByRole("button", {
    name: "了承して生成",
    exact: true,
  });
  await expect(approve).toBeEnabled({ timeout: 15_000 });
  await expect(page.getByTestId("generation-wave")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "まず1枚、見た目を確認", exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(2000);
  await expect(
    page.getByRole("heading", { name: "比較画像を確認", exact: true }),
  ).toHaveCount(0);
  await expect(approve).toBeEnabled();
  const enlarge = page.getByRole("button", {
    name: "参考画像を拡大",
    exact: true,
  });
  const preview = enlarge.getByRole("img", { name: "参考画像", exact: true });
  const zoomIcon = enlarge.getByTestId("zoom-icon");
  await expect(preview).toBeVisible();
  await page.mouse.move(0, 0);
  await expect(zoomIcon).toHaveCSS("opacity", "0");
  await preview.hover();
  await expect(zoomIcon).toHaveCSS("opacity", "1");
  await expect(enlarge).toHaveCSS("cursor", "zoom-in");
  await preview.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCSS("border-radius", "15px");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(enlarge).toBeFocused();
  await page.mouse.move(0, 0);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  await expect(enlarge).toBeFocused();
  await expect(zoomIcon).toHaveCSS("opacity", "1");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(approve).toBeEnabled();
  const regenerate = page.getByRole("button", {
    name: "作り直す",
    exact: true,
  });
  const expectReferenceActions = async () => {
    const back = await page
      .getByRole("button", { name: "条件へ戻る", exact: true })
      .boundingBox();
    const redo = await regenerate.boundingBox();
    expect.soft(redo!.y).toBe(back!.y);
    expect.soft(redo!.x - back!.x - back!.width).toBe(32);
  };
  await expectReferenceActions();
  await regenerate.click();
  const regenerateDialog = page.getByRole("dialog", {
    name: "参考画像を作り直す",
    exact: true,
  });
  const cancel = regenerateDialog.getByRole("button", {
    name: "キャンセル",
    exact: true,
  });
  await expect(cancel).toBeFocused();
  await cancel.click();
  await expect(regenerateDialog).toHaveCount(0);
  await expect(regenerate).toBeFocused();
  await expect(page.getByText(/残り\s*1\s*回/).first()).toBeVisible();
  await expect(page.getByTestId("generation-wave")).toHaveCount(0);
  await expect(approve).toBeEnabled();
  await page.screenshot({
    path: testInfo.outputPath("reference-approval.png"),
    fullPage: true,
  });
  await approve.evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });
  await expect(page.getByText(/^生成中\.*$/).first()).toBeVisible();
  await expect(
    page.getByRole("img", { name: "参考画像", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("generation-wave")).toHaveCount(2);
  await expect(
    page.getByRole("heading", { name: "比較画像を確認", exact: true }),
  ).toBeVisible({ timeout: 15_000 });
  await expectReferenceActions();
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "参考画像を拡大", exact: true }),
  ).toBeVisible();
  await completeSearch(page);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(page.getByText(exampleQuery, { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "メカニカルキーボード", exact: true }),
  ).toHaveCount(1);
});

test("history deletion is separated on the left and requires confirmation", async ({
  page,
}) => {
  await reviewConditions(page);
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await completeSearch(page);
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  const remove = page.getByRole("button", { name: "削除", exact: true });
  await remove.click();
  const dialog = page.getByRole("dialog", {
    name: "この履歴を削除しますか？",
    exact: true,
  });
  const confirm = dialog.getByRole("button", { name: "削除", exact: true });
  const cancel = dialog.getByRole("button", {
    name: "キャンセル",
    exact: true,
  });
  await expect(cancel).toBeFocused();
  await expect(confirm).toHaveCSS("width", "176px");
  await expect(confirm).toHaveCSS("height", "48px");
  await expect(confirm).toHaveCSS("border-radius", "100px");
  await expect(confirm).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(confirm).toHaveCSS(
    "box-shadow",
    "rgb(144, 16, 16) 0px 0px 0px 1px inset, rgb(144, 16, 16) 0px 0px 0px 1px inset",
  );
  await confirm.hover();
  await expect(confirm).toHaveCSS("background-color", "rgb(66, 66, 66)");
  const confirmBox = await confirm.boundingBox();
  const cancelBox = await cancel.boundingBox();
  expect(confirmBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(confirmBox!.x + confirmBox!.width).toBeLessThan(cancelBox!.x);
  await cancel.click();
  await expect(dialog).toHaveCount(0);
  await expect(remove).toBeFocused();
  await expect(page.getByText(exampleQuery, { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "メカニカルキーボード", exact: true }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "保存した検索結果", exact: true }),
  ).toBeVisible();
  await remove.click();
  await confirm.click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "検索履歴", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(exampleQuery, { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "メカニカルキーボード", exact: true }),
  ).toHaveCount(0);
});
