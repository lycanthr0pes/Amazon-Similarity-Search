import { expect, test, type Locator, type Page } from "@playwright/test";

test.beforeEach(async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin || url.pathname.startsWith("/api")) {
      await route.abort("blockedbyclient");
      throw new Error("The motion test attempted an external or API request.");
    }
    await route.continue();
  });
});

test("the toggle moves through intermediate positions and rapid reversal ends at the checked state", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const toggle = page.getByRole("switch", { name: /参考画像を使う/ });
  const thumb = page.getByTestId("toggle-thumb");
  const track = page.getByTestId("toggle-track");
  await expect(thumb).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
  const middle = await toggle.evaluate(async (element) => {
    const input = element as HTMLInputElement;
    const knob = document.querySelector<SVGElement>(
      '[data-testid="toggle-thumb"]',
    )!;
    getComputedStyle(input).backgroundColor;
    getComputedStyle(knob).transform;
    input.click();
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);
    const movement = knob.getAnimations()[0];
    const color = input.getAnimations()[0];
    for (const animation of [movement, color]) {
      if (animation) {
        animation.pause();
        animation.currentTime = 120;
      }
    }
    const sample = {
      moving: Boolean(movement),
      colorChanging: Boolean(color),
      x: new DOMMatrixReadOnly(getComputedStyle(knob).transform).m41,
      color: getComputedStyle(input).backgroundColor,
      duration: movement?.effect?.getTiming().duration,
    };
    for (const animation of [movement, color]) {
      animation?.finish();
    }
    return sample;
  });
  expect(middle.moving).toBe(true);
  expect(middle.colorChanging).toBe(true);
  expect(middle.duration).toBe(240);
  expect(middle.x).toBeGreaterThan(0);
  expect(middle.x).toBeLessThan(24);
  expect(middle.color).not.toBe("rgb(66, 66, 66)");
  expect(middle.color).not.toBe("rgb(58, 131, 247)");
  await expect(toggle).toBeChecked();
  await expect(thumb).toHaveCSS("transform", "matrix(1, 0, 0, 1, 24, 0)");

  await toggle.evaluate(async (element) => {
    const input = element as HTMLInputElement;
    input.click();
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);
    input.click();
  });
  await expect(toggle).toBeChecked();
  await expect(thumb).toHaveCSS("transform", "matrix(1, 0, 0, 1, 24, 0)");
  await expect(track).toHaveCSS("background-color", "rgb(58, 131, 247)");
  await toggle.focus();
  await page.keyboard.press("Space");
  await expect(toggle).not.toBeChecked();
  await expect(thumb).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
  await expect(track).toHaveCSS("background-color", "rgb(66, 66, 66)");
});

test("reduced motion changes the switch position and color without animation", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const toggle = page.getByRole("switch", { name: /参考画像を使う/ });
  const thumb = page.getByTestId("toggle-thumb");
  const track = page.getByTestId("toggle-track");
  for (const element of [thumb, track]) {
    await expect(element).toHaveCSS("transition-duration", "0s");
  }
  await toggle.check();
  await expect(thumb).toHaveCSS("transform", "matrix(1, 0, 0, 1, 24, 0)");
  await expect(track).toHaveCSS("background-color", "rgb(58, 131, 247)");
  for (const element of [thumb, track]) {
    expect(await element.evaluate((node) => node.getAnimations().length)).toBe(
      0,
    );
  }
});

async function openSyntheticHistory(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "amazon-explorer.mock-history.v1",
      JSON.stringify({
        version: 1,
        entries: [
          {
            id: "motion-history-fixture",
            createdAt: Date.now(),
            input: "履歴ボタンの表示確認用の合成入力。",
            conditions: {
              product: "合成キーボード",
              required: "ワイヤレス接続",
              preferred: "白い本体",
              excluded: "テンキー付き",
              budget: "5,000円〜15,000円",
            },
            useImages: false,
            products: [],
          },
        ],
      }),
    );
  });
  await page.goto("/");
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "検索履歴一覧" }).getByRole("listitem"),
  ).toHaveCount(1);
}

test("history actions use equal compact sizes with delete separated to the left", async ({
  page,
}, testInfo) => {
  await openSyntheticHistory(page);
  const card = page
    .getByRole("list", { name: "検索履歴一覧" })
    .getByRole("listitem");
  const remove = card.getByRole("button", { name: "削除", exact: true });
  const open = card.getByRole("button", { name: "開く", exact: true });
  for (const button of [remove, open]) {
    await expect(button).toHaveCSS("width", "96px");
    await expect(button).toHaveCSS("height", "36px");
    await expect(button).toHaveCSS("border-width", "0px");
    await expect(button).toHaveCSS("text-align", "center");
  }
  const removeBox = (await remove.boundingBox())!;
  const openBox = (await open.boundingBox())!;
  expect(removeBox.y).toBe(openBox.y);
  expect(openBox.x - removeBox.x - removeBox.width).toBeGreaterThanOrEqual(16);
  await expect(
    page.getByRole("button", { name: "検索へ戻る", exact: true }),
  ).toHaveCSS("width", "176px");
  await card.screenshot({ path: testInfo.outputPath("compact-history.png") });
});

async function expectDangerButton(button: Locator, page: Page) {
  await page.mouse.move(0, 0);
  await expect(button).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(button).toHaveCSS("color", "rgb(144, 16, 16)");
  await expect(button).toHaveCSS(
    "box-shadow",
    "rgb(144, 16, 16) 0px 0px 0px 1px inset, rgb(144, 16, 16) 0px 0px 0px 1px inset",
  );
  await expect(button).toHaveCSS("border-width", "0px");
  await button.hover();
  await expect(button).toHaveCSS("background-color", "rgb(66, 66, 66)");
  await expect(button).toHaveCSS("color", "rgb(144, 16, 16)");
  await expect(button).toHaveCSS("border-width", "0px");
}

test("every delete action has danger styling in the list, saved results, and confirmation", async ({
  page,
}) => {
  await openSyntheticHistory(page);
  const remove = page.getByRole("button", { name: "削除", exact: true });
  await expectDangerButton(remove, page);
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "保存した検索結果", exact: true }),
  ).toBeVisible();
  await expectDangerButton(remove, page);
  await remove.click();
  const dialog = page.getByRole("dialog", {
    name: "この履歴を削除しますか？",
    exact: true,
  });
  const confirm = dialog.getByRole("button", { name: "削除", exact: true });
  await expectDangerButton(confirm, page);
  await expect(confirm).toHaveCSS("width", "176px");
  await expect(confirm).toHaveCSS("height", "48px");
  await dialog.getByRole("button", { name: "キャンセル", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(remove).toBeFocused();
});

test("windows and buttons use circular corners and integer frame positions", async ({
  page,
}) => {
  await page.goto("/");
  const panel = page.locator("section").first();
  await expect.soft(panel).toHaveCSS("corner-shape", "superellipse(1)");
  await expect(panel).toHaveCSS("border-radius", "15px");
  const primary = page.getByRole("button", { name: "条件を整理", exact: true });
  await expect.soft(primary).toHaveCSS("corner-shape", "superellipse(1)");
  await expect(primary).toHaveCSS("border-radius", "100px");
  await page.evaluate(() => document.fonts.ready);
  for (const frame of await page
    .locator("header, section, button, textarea")
    .all()) {
    const box = (await frame.boundingBox())!;
    for (const value of [box.x, box.y, box.width, box.height]) {
      expect.soft(value).toBe(Math.round(value));
    }
  }
  await openSyntheticHistory(page);
  await page.getByRole("button", { name: "削除", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "この履歴を削除しますか？",
    exact: true,
  });
  await expect.soft(dialog).toHaveCSS("corner-shape", "superellipse(1)");
  await expect(dialog).toHaveCSS("border-radius", "15px");
});
