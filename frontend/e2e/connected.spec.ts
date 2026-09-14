import { expect, test } from "@playwright/test";

for (const [kind, message] of [
  ["network", "通信に失敗しました（network）"],
  ["json", "応答をJSONとして読み取れませんでした（json）"],
  ["schema", "schema：段階・更新番号"],
] as const) {
  test(`connection diagnosis distinguishes ${kind} errors`, async ({
    page,
  }) => {
    await page.route("**/api/state", (route) => {
      if (kind === "network") {
        return route.abort("failed");
      }
      return route.fulfill(
        kind === "json"
          ? { body: "private response" }
          : { json: { stage: "private stage", revision: 0 } },
      );
    });
    await page.goto("/?mode=connected");
    await expect(page.getByRole("alert")).toContainText(message);
    expect(
      await page.evaluate(() => JSON.stringify(sessionStorage)),
    ).not.toContain("private");
  });
}

test("connection diagnosis survives recovery and reload without repeating a command", async ({
  page,
}) => {
  let failed = true;
  let posts = 0;
  page.on("request", (request) => {
    if (request.method() === "POST") {
      posts += 1;
    }
  });
  await page.route("**/api/state", (route) =>
    route.fulfill(
      failed
        ? { status: 503, body: "private response must not be recorded" }
        : {
            json: {
              stage: "idle",
              revision: 0,
              editable: true,
              input: "合成入力",
            },
          },
    ),
  );
  await page.goto("/?mode=connected");
  await expect(page.getByRole("alert")).toContainText("HTTP 503");
  failed = false;
  await expect(
    page.getByRole("button", { name: "条件を整理", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByText("接続診断", { exact: true }).press("Enter");
  await expect(page.getByLabel("接続診断")).toContainText("HTTP 503");
  await page.reload();
  await page.getByText("接続診断", { exact: true }).press("Enter");
  await expect(page.getByLabel("接続診断")).toContainText("HTTP 503");
  const stored = await page.evaluate(() => JSON.stringify(sessionStorage));
  expect(stored).not.toContain("private");
  expect(stored).not.toContain("合成入力");
  expect(posts).toBe(0);
});

test("an open browser recovers when the server restarts its revision counter", async ({
  page,
}) => {
  let restarted = false;
  const commands: Record<string, unknown>[] = [];
  await page.route("**/api/state", async (route) => {
    await route.fulfill({
      json: {
        stage: restarted ? "idle" : "working",
        workingAction: restarted ? undefined : "start",
        revision: restarted ? 0 : 5,
        instanceId: restarted ? "b".repeat(32) : "a".repeat(32),
        editable: true,
        input: "マグカップ。丸みのある形。",
      },
    });
  });
  await page.route("**/api/command", async (route) => {
    commands.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        stage: "working",
        workingAction: "start",
        revision: 1,
        instanceId: "b".repeat(32),
        editable: true,
      },
    });
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByText("条件を整理しています", { exact: true }),
  ).toBeVisible();
  restarted = true;
  const organize = page.getByRole("button", {
    name: "条件を整理",
    exact: true,
  });
  await expect(organize).toBeEnabled();
  expect(commands).toHaveLength(0);
  await organize.press("Enter");
  await expect.poll(() => commands.length).toBe(1);
  expect(commands[0].revision).toBe(0);
  expect(commands[0].instanceId).toBe("b".repeat(32));
});

test("an expired server confirmation hides execution controls and retains the preview", async ({
  page,
}) => {
  let expired = false;
  let submissions = 0;
  page.on("request", (request) => {
    if (request.method() === "POST") {
      submissions += 1;
    }
  });
  await page.route("**/api/state", async (route) => {
    await route.fulfill({
      json: {
        stage: expired ? "expired" : "reference",
        revision: expired ? 3 : 2,
        mode: "fixture",
        input: "合成の期限検証",
        expiresAt: "2000-01-01T00:00:00+00:00",
        images: [
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3e8AAAAASUVORK5CYII=",
        ],
        message: expired
          ? "確認の期限が切れました。今回の実行は終了しています。"
          : undefined,
      },
    });
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("確認期限：", { exact: false })).toBeVisible();
  expired = true;
  await expect(
    page.getByRole("heading", { name: "確認の期限が切れました", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("img", { name: "参考画像", exact: true }),
  ).toBeVisible();
  expect(submissions).toBe(0);
});

test("browser confirmations reach a local API result without duplicate submission", async ({
  page,
}) => {
  const commands: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.name));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:8766") {
      await route.abort();
      throw new Error("Unexpected external request");
    }
    if (url.pathname === "/api/command") {
      commands.push(route.request().postDataJSON().action);
      if (commands.length === 1) {
        await route.fetch();
        await route.abort("failed");
        return;
      }
    }
    await route.continue();
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByText("オフライン接続テスト · 固定の合成応答を使っています。", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "探している商品・条件" })
    .fill("ケース。赤が不要ではない。");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "文章を修正してください", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("修正箇所：赤が不要ではない", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "探している商品・条件" })
    .fill("青いケース。できれば2000円以下。取っ手がなくてもよい。");
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "希望条件", exact: true }),
  ).toHaveValue("2000円以下");
  await expect(
    page.getByText("検索に使わない条件：取っ手", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "商品名", exact: true }),
  ).toHaveValue("青いケース");
  await page.getByRole("switch").check();
  await page
    .getByRole("textbox", { name: "商品名", exact: true })
    .fill("白いケース");
  await page
    .getByRole("textbox", { name: "優先条件", exact: true })
    .fill("1500円以下");
  await page.getByRole("textbox", { name: "希望条件", exact: true }).fill("");
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "参考画像を生成", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toBeVisible();
  expect(commands).toEqual(["start", "revise", "revise", "reference"]);
  expect((await (await page.request.get("/api/state")).json()).input).toBe(
    "白いケース。1500円以下。取っ手がなくてもよい。",
  );
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "検索", exact: true })
    .evaluate((element: HTMLButtonElement) => {
      element.click();
      element.click();
    });
  await expect(
    page.getByRole("button", { name: "結果を見る", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "合成マグカップ", exact: true }),
  ).toBeVisible();
  expect(commands).toEqual([
    "start",
    "revise",
    "revise",
    "reference",
    "comparison",
    "final",
    "search",
  ]);
  await expect(
    page.getByRole("img", { name: "合成マグカップの商品画像", exact: true }),
  ).toBeVisible();
  await page.getByText("検索詳細", { exact: true }).click();
  await expect(page.getByRole("table")).toContainText("タイトル一致");
  await expect(page.getByText("画像同士：75.0", { exact: true })).toBeVisible();
  await expect(
    page.getByText("文章と画像：85.0", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "合成マグカップ", exact: true }),
  ).toBeVisible();
  expect(commands).toHaveLength(7);
  expect(errors).toEqual([]);
});

test("stored English Amazon links open the same product with Japanese requested", async ({
  page,
}) => {
  let posts = 0;
  page.on("request", (request) => {
    if (request.method() === "POST") posts += 1;
  });
  await page.route("**/api/state", (route) =>
    route.fulfill({
      json: {
        stage: "complete",
        revision: 5,
        mode: "fixture",
        saved: true,
        products: [
          {
            title: "合成の商品",
            titleEn: "Synthetic Product",
            titleEnStatus: "available",
            scores: {
              title: { score_ja: 0.5, score_en: 0.8, score: 0.8 },
              conditions: [],
              image: 0.6,
            },
            price: 2000,
            url: "https://www.amazon.co.jp/-/en/Synthetic/dp/B000000001?language=en_US&th=1",
            required: "一致",
            appearance: "外観は未確認",
          },
        ],
      },
    }),
  );
  await page.goto("/?mode=connected");
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  const englishTitle = page.locator('[lang="en"]', {
    hasText: "Synthetic Product",
  });
  await expect(englishTitle).toBeHidden();
  const details = page.locator("details").filter({
    has: page.locator("summary", { hasText: "検索詳細" }),
  });
  await expect(
    page.getByRole("list", { name: "検索結果" }).locator("details"),
  ).toHaveCount(1);
  await expect(details).toHaveCSS("background-color", "rgb(33, 33, 33)");
  await details.locator("summary").click();
  await expect(details.locator(":scope > div > p").first()).toHaveText(
    "英語タイトル：Synthetic Product",
  );
  await expect(details.getByRole("table")).toBeVisible();
  await expect(details).not.toContainText("必須条件：");
  await expect(details).not.toContainText("外観は未確認");
  await expect(details).not.toContainText("仕様が確認できたことを保証しません");
  await expect(
    details.locator('[lang="en"]', { hasText: "Synthetic Product" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Amazonで見る", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "合成の商品", exact: true }),
  ).toHaveAttribute(
    "href",
    "https://www.amazon.co.jp/dp/B000000001?language=ja_JP&th=1",
  );
  await details.locator("summary").click();
  await expect(englishTitle).toBeHidden();
  expect(posts).toBe(0);
});

test("history survives reload and returns to an unchanged search without POST", async ({
  page,
}) => {
  let posts = 0;
  let unavailable = false;
  const id = "h".repeat(43);
  const item = {
    id,
    summary: "合成の保存条件",
    completedAt: "2026-09-12T00:00:00Z",
    expiresAt: "2026-10-12T00:00:00Z",
    count: 1,
  };
  await page.route("**/api/state", (r) =>
    r.fulfill({
      json: {
        stage: "idle",
        revision: 0,
        editable: true,
        input: "編集中の合成入力",
        historyAvailable: true,
      },
    }),
  );
  await page.route("**/api/history", (r) =>
    unavailable
      ? r.fulfill({ status: 503, json: {} })
      : r.fulfill({ json: { items: [item] } }),
  );
  await page.route("**/api/history/" + id, (r) =>
    r.fulfill({
      json: {
        ...item,
        view: {
          stage: "complete",
          revision: 0,
          saved: true,
          images: [],
          products: [
            {
              title: "保存した合成商品",
              price: 1234,
              url: null,
              required: "一致",
              appearance: "外観は未確認",
            },
          ],
        },
      },
    }),
  );
  page.on("request", (r) => {
    if (r.method() === "POST") posts++;
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByRole("textbox", { name: "探している商品・条件" }),
  ).toHaveValue("編集中の合成入力");
  await page
    .getByRole("textbox", { name: "探している商品・条件" })
    .fill("まだ送っていない文章");
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "検索履歴", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "再読込", exact: true }),
  ).toHaveCount(0);
  const savedPeriod =
    /^2026\/09\/12 \d{2}:\d{2} から 2026\/10\/12 \d{2}:\d{2}まで保存$/;
  await expect(page.getByText(savedPeriod)).toBeVisible();
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "保存した合成商品", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(savedPeriod)).toBeVisible();
  await page.getByRole("button", { name: "検索へ戻る", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "探している商品・条件" }),
  ).toHaveValue("まだ送っていない文章");
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "保存した合成商品", exact: true }),
  ).toBeVisible();
  for (const text of [
    "価格や商品ページの内容は保存時点の情報です。履歴を開いても検索や画像生成は再実行しません。",
    "元の入力全文・条件の個別名称・商品画像は、この履歴には保存されていません。",
  ]) {
    await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  }
  await page.getByRole("button", { name: "履歴へ戻る", exact: true }).click();
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "保存した合成商品", exact: true }),
  ).toBeVisible();
  unavailable = true;
  await page.getByRole("button", { name: "履歴へ戻る", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "検索履歴を読み込めませんでした",
  );
  await expect(page.getByText("合成の保存条件", { exact: true })).toBeVisible();
  expect(posts).toBe(0);
});

test("new ranking shows negative exclusions and reviews with the saved priority", async ({
  page,
}) => {
  let old = false;
  const product = {
    title: "順位確認用の合成商品",
    price: 1000,
    url: null,
    required: "一致",
    appearance: "外観は未確認",
    reviewRating: 4.5,
    scores: {
      title: { score_ja: 0.5, score_en: 0.8, score: 0.8 },
      image: 0.6,
      total: 0.7,
      conditions: [
        {
          requirement_id: "exclude-1",
          strength: "excluded",
          score_ja: 0.2,
          score_en: 0.6,
          score: 0.6,
        },
      ],
    },
  };
  await page.route("**/api/state", (r) =>
    r.fulfill({
      json: {
        stage: "complete",
        revision: 1,
        saved: true,
        sortProfile: old
          ? "title-image-conditions-v1"
          : "excluded-title-conditions-image-review-v1",
        products: [product],
      },
    }),
  );
  await page.goto("/?mode=connected");
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await page.getByText("検索詳細", { exact: true }).click();
  await expect(
    page.getByText("レビュースコア：4.5 / 5", { exact: true }),
  ).toBeVisible();
  const row = page.locator("tbody tr").nth(1);
  await expect(row.locator("td")).toHaveText(["-20.0", "-60.0", "-60.0"]);
  await expect(page.getByText(/^一致点は|^順位は/)).toHaveCount(0);
  await expect(
    page.getByText("日本語・英語の比較と採用点", { exact: true }),
  ).toHaveCount(0);
  old = true;
  await page.reload();
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await page.getByText("検索詳細", { exact: true }).click();
  await expect(row.locator("td")).toHaveText(["20.0", "60.0", "60.0"]);
  await expect(page.getByText(/^一致点は|^順位は/)).toHaveCount(0);
  await expect(
    page.getByText("日本語・英語の比較と採用点", { exact: true }),
  ).toHaveCount(0);
});

test("image-free search uses final confirmation and survives reload without image commands", async ({
  page,
}) => {
  const commands: string[] = [];
  const errors: string[] = [];
  const deletions: string[] = [];
  let failure = 0;
  page.on("pageerror", (error) => errors.push(error.name));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:8764") {
      await route.abort();
      throw new Error("Unexpected external request");
    }
    if (url.pathname === "/api/history/command") {
      deletions.push(route.request().postDataJSON().id);
      if (failure === 0) {
        failure++;
        await route.fulfill({ status: 503, json: {} });
        return;
      }
      if (failure === 1) {
        failure++;
        await route.fetch();
        await route.abort("failed");
        return;
      }
    }
    if (url.pathname === "/api/command")
      commands.push(route.request().postDataJSON().action);
    await route.continue();
  });
  await page.goto("http://127.0.0.1:8764/?mode=connected");
  const source = "マグカップ。できれば3000円以下。取っ手がなくてもよい。";
  await expect(
    page.getByRole("textbox", { name: "探している商品・条件" }),
  ).toHaveValue("マグカップ。3000円以下。取っ手がなくてもよい。");
  await page
    .getByRole("textbox", { name: "探している商品・条件" })
    .fill(source);
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await page
    .getByRole("button", { name: "画像なしで進む", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("画像比較なし：", { exact: false }),
  ).toBeVisible();
  expect(commands).toEqual(["start", "without_images"]);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "検索", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "検索", exact: true })
    .evaluate((element: HTMLButtonElement) => {
      element.click();
      element.click();
    });
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "合成マグカップの商品画像", exact: true }),
  ).toBeVisible();
  await page.getByText("検索詳細", { exact: true }).click();
  await expect(
    page.getByText("画像評価：未使用", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("参考合成点", { exact: false })).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "結果を見る", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "検索履歴", exact: true }).click();
  await page.getByRole("button", { name: "開く", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "保存された検索内容", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("main").getByText(source, { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("main")
      .locator("dl > div")
      .filter({ hasText: "指定なし" })
      .filter({ hasText: "取っ手がなくてもよい" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("main")
      .locator("dl > div")
      .filter({ hasText: "希望条件" })
      .filter({ hasText: "できれば3000円以下" }),
  ).toBeVisible();
  await page.getByRole("main").getByText("検索詳細", { exact: true }).click();
  await expect(page.getByRole("main").locator("tbody")).toContainText(
    "3000円以下",
  );
  await expect(
    page.getByText("画像比較なしで保存された結果です。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "合成マグカップ", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("画像比較なしで保存された結果です。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "合成マグカップの商品画像", exact: true }),
  ).toBeVisible();
  const before = await (
    await page.request.get("http://127.0.0.1:8764/api/state")
  ).json();
  const deleteButton = page.getByRole("button", { name: "削除", exact: true });
  await deleteButton.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("削除後は復元できません");
  await dialog.getByRole("button", { name: "キャンセル", exact: true }).click();
  await expect(deleteButton).toBeFocused();
  expect(deletions).toEqual([]);
  await deleteButton.click();
  await dialog
    .getByRole("button", { name: "削除", exact: true })
    .evaluate((button: HTMLButtonElement) => {
      button.click();
      button.click();
    });
  await expect(
    page.getByText("履歴を削除できませんでした", { exact: true }),
  ).toBeVisible();
  expect(deletions).toHaveLength(1);
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await expect(
    page.getByText("履歴を削除できませんでした", { exact: true }),
  ).toBeVisible();
  expect(deletions).toHaveLength(2);
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await expect(
    page.getByText("保存された検索結果はまだありません", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("保存された検索結果はまだありません", { exact: true }),
  ).toBeVisible();
  expect(deletions).toHaveLength(3);
  expect(new Set(deletions).size).toBe(1);
  expect(
    await (await page.request.get("http://127.0.0.1:8764/api/state")).json(),
  ).toEqual(before);
  expect(commands).toEqual(["start", "without_images", "search"]);
  expect(errors).toEqual([]);
});

test("expiry cleanup failure offers a local retry without search commands", async ({
  page,
}) => {
  let pending = true;
  const actions: unknown[] = [];
  await page.route("**/api/state", (route) =>
    route.fulfill({
      json: {
        stage: "idle",
        revision: 0,
        mode: "fixture",
        historyAvailable: true,
      },
    }),
  );
  await page.route("**/api/history", (route) =>
    route.fulfill({ json: { items: [], cleanupPending: pending } }),
  );
  await page.route("**/api/history/command", async (route) => {
    actions.push(route.request().postDataJSON());
    pending = false;
    await route.fulfill({ json: { deletedCount: 1 } });
  });
  await page.goto("/?mode=connected#history");
  await expect(
    page.getByText("期限切れデータを削除できませんでした。", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "期限切れ削除を再試行", exact: true })
    .click();
  await expect(
    page.getByText("期限切れデータを削除できませんでした。", { exact: false }),
  ).toHaveCount(0);
  expect(actions).toEqual([{ action: "purge_expired" }]);
});

test("saved product images and condition names display after reload without network images", async ({
  page,
}) => {
  const id = "p".repeat(43);
  const thumbnail =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3e8AAAAASUVORK5CYII=";
  const item = {
    id,
    summary: "短い合成要約",
    completedAt: "2026-09-12T00:00:00Z",
    expiresAt: "2026-10-12T00:00:00Z",
    count: 1,
  };
  let requests = 0;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:8766" || request.method() === "POST") {
      requests++;
      await route.abort();
      return;
    }
    if (url.pathname === "/api/state")
      return route.fulfill({
        json: { stage: "idle", revision: 0, input: "", historyAvailable: true },
      });
    if (url.pathname === "/api/history")
      return route.fulfill({ json: { items: [item] } });
    if (url.pathname === "/api/history/" + id)
      return route.fulfill({
        json: {
          ...item,
          view: {
            stage: "complete",
            revision: 0,
            saved: true,
            historyContentAvailable: true,
            input: "合成商品の元入力全文。",
            conditionReview: [],
            conditionLabels: { "condition-001": "光学解像度600dpi以上" },
            images: [],
            products: [
              {
                title: "画像保存の合成商品",
                price: 1000,
                url: null,
                required: "一致",
                appearance: "外観は未確認",
                thumbnail,
                scores: {
                  title: { score_ja: 1, score_en: null, score: 1 },
                  conditions: [
                    {
                      requirement_id: "condition-001",
                      strength: "required",
                      score_ja: 1,
                      score_en: null,
                      score: 1,
                    },
                  ],
                },
              },
            ],
          },
        },
      });
    await route.continue();
  });
  await page.goto("/?mode=connected#history/" + id);
  for (let attempt = 0; attempt < 2; attempt++) {
    await expect(
      page.getByText("合成商品の元入力全文。", { exact: true }),
    ).toBeVisible();
    const image = page.getByRole("img", {
      name: "画像保存の合成商品の商品画像",
      exact: true,
    });
    await expect(image).toBeVisible();
    await expect(image).toHaveJSProperty("naturalWidth", 1);
    await expect(image).toHaveAttribute("src", thumbnail);
    await page.getByText("検索詳細", { exact: true }).click();
    await expect(page.locator("tbody")).toContainText("光学解像度600dpi以上");
    await expect(
      page.getByText(
        "元の入力全文・条件の個別名称・商品画像は、この履歴には保存されていません。",
        { exact: true },
      ),
    ).toHaveCount(0);
    if (attempt === 0) await page.reload();
  }
  expect(requests).toBe(0);
});

test("image preference reaches preparation and enabling images requires reorganization", async ({
  page,
}) => {
  let state: Record<string, unknown> = {
    stage: "idle",
    revision: 0,
    editable: true,
    input: "ケース。羽根付き。",
  };
  const commands: Record<string, unknown>[] = [];
  await page.route("**/api/state", (route) => route.fulfill({ json: state }));
  await page.route("**/api/command", async (route) => {
    const command = route.request().postDataJSON();
    commands.push(command);
    state = {
      ...state,
      stage: "query",
      revision: commands.length,
      canRevise: true,
      productName: "ケース",
      conditionText: "羽根付き。",
      queries: ["ケース"],
      conditions: ["羽根付き"],
      canSkipImages: true,
      canGenerateImages: command.imageMode === "on",
      imageMode: command.imageMode === "off" ? "off" : undefined,
      images: [],
    };
    await route.fulfill({ json: state });
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByRole("textbox", { name: "探している商品・条件" }),
  ).toHaveValue("ケース。羽根付き。");
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "画像なしで進む", exact: true }),
  ).toBeEnabled();
  expect(commands[0].imageMode).toBe("off");
  await page.getByRole("switch").check();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeEnabled();
  expect(
    commands.map((command) => [command.action, command.imageMode]),
  ).toEqual([
    ["start", "off"],
    ["revise", "on"],
  ]);
});

test("source-order weights survive real fixture scoring and saved history", async ({
  page,
}) => {
  await page.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== "http://127.0.0.1:8764") {
      throw new Error("Unexpected external request");
    }
    await route.continue();
  });
  await page.goto("http://127.0.0.1:8764/?mode=connected");
  await page
    .getByRole("button", { name: "新しく検索", exact: true })
    .press("Enter");
  await page
    .getByRole("textbox", { name: "探している商品・条件" })
    .fill("マグカップ。電子レンジ対応。食洗機対応。");
  for (const name of ["条件を整理", "画像なしで進む", "検索", "結果を見る"]) {
    const button = page.getByRole("button", { name, exact: true });
    await expect(button).toBeEnabled();
    await button.press("Enter");
  }
  await page.getByText("検索詳細", { exact: true }).press("Enter");
  const table = page.getByRole("table", { name: "点数の内訳" });
  await expect(
    table.getByRole("columnheader", { name: "重み", exact: true }),
  ).toBeVisible();
  await expect(
    table.getByRole("row").filter({ hasText: "電子レンジ" }),
  ).toContainText("2倍");
  await expect(
    table.getByRole("row").filter({ hasText: "食洗機" }),
  ).toContainText("1倍");
  await page
    .getByRole("button", { name: "検索履歴", exact: true })
    .press("Enter");
  await page
    .getByRole("button", { name: "開く", exact: true })
    .first()
    .press("Enter");
  await page.reload();
  await page
    .getByRole("main")
    .getByText("検索詳細", { exact: true })
    .press("Enter");
  await expect(
    table.getByRole("row").filter({ hasText: "電子レンジ" }),
  ).toContainText("2倍");
  await expect(
    table.getByRole("row").filter({ hasText: "食洗機" }),
  ).toContainText("1倍");
});
