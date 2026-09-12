import { expect, test } from "@playwright/test";

const product = {
  title: "合成商品",
  price: 1000,
  url: null,
  required: "未確認",
  appearance: "外観は未確認",
  thumbnail:
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3e8AAAAASUVORK5CYII=",
};
test("connected input shares the mock header, step label and image switch", async ({
  page,
}) => {
  await page.route("**/api/state", (r) =>
    r.fulfill({
      json: {
        stage: "idle",
        revision: 0,
        editable: true,
        input: "",
        historyAvailable: true,
        canReset: true,
      },
    }),
  );
  await page.goto("/?mode=connected");
  await expect(
    page.getByRole("button", { name: "新しく検索", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("STEP 01 / 05", { exact: true })).toBeVisible();
  await expect(page.getByRole("switch")).not.toBeChecked();
  await expect(
    page.getByText(
      "商品と条件を入力してください。条件を整理した後、画像比較を使うか選べます。",
      { exact: true },
    ),
  ).toHaveCount(0);
});
test("connected results share count, rank, condition disclosure, zoom and back to top", async ({
  page,
}) => {
  await page.route("**/api/state", (r) =>
    r.fulfill({
      json: {
        stage: "complete",
        revision: 1,
        saved: true,
        products: Array.from({ length: 24 }, (_, i) => ({
          ...product,
          title: `合成商品${i + 1}`,
        })),
      },
    }),
  );
  await page.goto("/?mode=connected");
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "表示件数" })).toHaveValue(
    "10",
  );
  await expect(
    page.getByRole("list", { name: "検索結果" }).locator(":scope > li"),
  ).toHaveCount(10);
  await page.getByRole("combobox", { name: "表示件数" }).selectOption("24");
  await expect(
    page.getByRole("list", { name: "検索結果" }).locator(":scope > li"),
  ).toHaveCount(24);
  await expect(page.getByText("#24", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "合成商品1を拡大", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "トップに戻る" }),
  ).toBeVisible();
});

for (const [action, title, step] of [
  ["start", "条件を整理しています", "STEP 01 / 05"],
  ["reference", "参考画像を準備", "STEP 02 / 05"],
  ["comparison", "比較画像を準備", "STEP 02 / 05"],
  ["search", "商品を調査", "STEP 04 / 05"],
] as const) {
  test(`working ${action} uses the matching mock screen`, async ({ page }) => {
    await page.route("**/api/state", (r) =>
      r.fulfill({
        json: {
          stage: "working",
          revision: 2,
          workingAction: action,
          input: "合成入力",
          editable: true,
          researchStep: 0,
          conditions: ["丸い形"],
          images: action === "comparison" ? [product.thumbnail] : [],
        },
      }),
    );
    await page.goto("/?mode=connected");
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await expect(page.getByText(step, { exact: true })).toBeVisible();
    if (action === "search") {
      await expect(
        page.getByRole("list", { name: "商品調査の進行" }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "結果を見る", exact: true }),
      ).toBeDisabled();
    } else if (action !== "start") {
      await expect(
        page.getByRole("button", { name: "生成中", exact: true }),
      ).toBeDisabled();
    }
    await expect(
      page.getByRole("button", { name: "新しく検索", exact: true }),
    ).toBeDisabled();
  });
}

test("regeneration confirms once, resets image approval and returning requires applying edits", async ({
  page,
}) => {
  let state: Record<string, unknown> = {
    stage: "reference",
    revision: 1,
    input: "合成入力",
    editable: true,
    canRevise: true,
    canReset: true,
    referenceRemaining: 1,
    canRegenerate: true,
    canSkipImages: true,
    conditions: ["丸い形"],
    images: [product.thumbnail],
  };
  const commands: string[] = [];
  await page.route("**/api/state", (r) => r.fulfill({ json: state }));
  await page.route("**/api/command", (r) => {
    const command = r.request().postDataJSON();
    commands.push(command.action);
    state = {
      ...state,
      revision: Number(state.revision) + 1,
      ...(command.action === "regenerate"
        ? { referenceRemaining: 0, canRegenerate: false }
        : command.action === "comparison"
          ? {
              stage: "comparison",
              images: [product.thumbnail, product.thumbnail],
            }
          : command.action === "final"
            ? { stage: "final" }
            : {
                stage: "query",
                input: command.source,
                images: [],
                queries: ["合成"],
                canGenerateImages: true,
              }),
    };
    return r.fulfill({ json: state });
  });
  await page.goto("/?mode=connected");
  const remake = page.getByRole("button", { name: "作り直す", exact: true });
  await remake.click();
  await page.keyboard.press("Escape");
  await expect(remake).toBeFocused();
  expect(commands).toEqual([]);
  await remake.click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "作り直す", exact: true })
    .click();
  await expect(remake).toBeDisabled();
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await page
    .getByRole("button", { name: "比較画像：丸い形を変更を拡大", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "前へ", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "前へ", exact: true }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await page.getByRole("button", { name: "条件へ戻る", exact: true }).click();
  await page
    .getByRole("textbox", { name: "探している商品・条件" })
    .fill("変更した合成入力");
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "条件を確認", exact: true }),
  ).toBeVisible();
  expect(commands).toEqual(["regenerate", "comparison", "final", "revise"]);
  await expect(page.getByRole("img")).toHaveCount(0);
});

test("cancel confirmation and unsaved-result discard require explicit actions", async ({
  page,
}) => {
  let state: Record<string, unknown> = {
    stage: "working",
    revision: 1,
    workingAction: "search",
    input: "合成",
    researchStep: 0,
    canCancel: true,
    editable: true,
  };
  const commands: string[] = [];
  await page.route("**/api/state", (r) => r.fulfill({ json: state }));
  await page.route("**/api/command", (r) => {
    const command = r.request().postDataJSON();
    commands.push(command.action);
    state =
      command.action === "cancel"
        ? {
            stage: "cancelled",
            revision: 2,
            input: "合成",
            message: "検索を中止しました。",
            canReset: true,
            editable: true,
          }
        : {
            stage: "idle",
            revision: 4,
            input: "",
            editable: true,
            canReset: true,
          };
    return r.fulfill({ json: state });
  });
  await page.goto("/?mode=connected");
  await page.getByRole("button", { name: "検索を中止", exact: true }).click();
  await page.getByRole("button", { name: "キャンセル", exact: true }).click();
  expect(commands).toEqual([]);
  await page.getByRole("button", { name: "検索を中止", exact: true }).click();
  await page.getByRole("button", { name: "中止する", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "検索を中止しました", exact: true }),
  ).toBeVisible();
  state = {
    stage: "complete",
    revision: 3,
    saved: false,
    canRetrySave: true,
    canReset: true,
    input: "合成",
    products: [product],
  };
  await page.reload();
  await expect(
    page.getByRole("button", { name: "保存を再試行", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "新しく検索", exact: true }).click();
  await page.getByRole("button", { name: "キャンセル", exact: true }).click();
  expect(commands).toEqual(["cancel"]);
  await page.getByRole("button", { name: "新しく検索", exact: true }).click();
  await page
    .getByRole("button", { name: "破棄して新しく検索", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "探している商品・条件" }),
  ).toHaveValue("");
  expect(commands).toEqual(["cancel", "reset"]);
});

test("an initial image preference cannot block a query without appearance conditions", async ({
  page,
}) => {
  let view: Record<string, unknown> = {
    stage: "idle",
    revision: 0,
    input: "マグカップ",
    editable: true,
    canReset: true,
  };
  await page.route("**/api/state", (r) => r.fulfill({ json: view }));
  await page.route("**/api/command", (r) => {
    view = {
      ...view,
      stage: "query",
      revision: 1,
      queries: ["マグカップ"],
      conditions: [],
      canRevise: true,
      canGenerateImages: false,
      canSkipImages: true,
    };
    return r.fulfill({ json: view });
  });
  await page.goto("/?mode=connected");
  await page.getByRole("switch").check();
  await page.getByRole("button", { name: "条件を整理", exact: true }).click();
  await expect(page.getByRole("switch")).not.toBeChecked();
  await expect(
    page.getByRole("button", { name: "画像なしで進む", exact: true }),
  ).toBeEnabled();
});

test("product and condition edits refresh terms before continuing", async ({
  page,
}) => {
  let state = {
    stage: "query",
    revision: 1,
    editable: true,
    canRevise: true,
    input: "マグカップ。できれば赤。",
    productName: "マグカップ",
    conditionText: "できれば赤。",
    queries: ["マグカップ"],
    conditionReview: [
      {
        start: 6,
        end: 11,
        quote: "できれば赤",
        target: "赤",
        strength: "preferred",
        reason: "preference_prefix",
      },
    ],
    canSkipImages: true,
    canGenerateImages: false,
  };
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/state", (r) => r.fulfill({ json: state }));
  await page.route("**/api/command", (r) => {
    const payload = r.request().postDataJSON();
    requests.push(payload);
    state = {
      ...state,
      revision: state.revision + 1,
      input: payload.source,
      productName: "タンブラー",
      conditionText: "できれば青。",
      queries: ["タンブラー"],
      conditionReview: [
        {
          start: 6,
          end: 11,
          quote: "できれば青",
          target: "青",
          strength: "preferred",
          reason: "preference_prefix",
        },
      ],
    };
    return r.fulfill({ json: state });
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByRole("textbox", { name: "商品名", exact: true }),
  ).toHaveValue("マグカップ");
  await expect(
    page.locator("summary", { hasText: "入力した文章" }),
  ).toHaveCount(0);
  await expect(
    page.locator("summary", { hasText: "検索語を確認・修正" }),
  ).toHaveCount(0);
  await page.getByRole("textbox", { name: "商品名", exact: true }).fill("");
  await expect(
    page.getByRole("button", { name: "変更を反映", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("textbox", { name: "商品名", exact: true })
    .fill("マグカップ");
  await expect(
    page.getByRole("button", { name: "変更を反映", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "商品名", exact: true })
    .fill("タンブラー");
  await page.getByRole("textbox", { name: "希望条件", exact: true }).fill("青");
  await expect(
    page.getByRole("button", { name: "画像なしで進む", exact: true }),
  ).toBeDisabled();
  expect(requests).toHaveLength(0);
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "画像なしで進む", exact: true }),
  ).toBeEnabled();
  expect(requests).toHaveLength(1);
  expect(requests[0]).toMatchObject({
    action: "revise",
    source: "タンブラー。できれば青。",
  });
});

test("condition groups stay editable when empty and use comma-separated entries", async ({
  page,
}) => {
  const input = "マグカップ。電子レンジ対応。3000円以下。";
  let state = {
    stage: "query",
    revision: 1,
    editable: true,
    canRevise: true,
    input,
    productName: "マグカップ",
    conditionText: "電子レンジ対応。3000円以下。",
    queries: ["マグカップ"],
    canSkipImages: true,
    canGenerateImages: true,
    conditionReview: [
      {
        start: 6,
        end: 13,
        quote: "電子レンジ対応",
        target: "電子レンジ対応",
        strength: "required",
        reason: "explicit_condition",
      },
      {
        start: 14,
        end: 21,
        quote: "3000円以下",
        target: "3000円以下",
        strength: "required",
        reason: "explicit_condition",
      },
    ],
  };
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/state", (r) => r.fulfill({ json: state }));
  await page.route("**/api/command", (r) => {
    const payload = r.request().postDataJSON();
    requests.push(payload);
    return r.fulfill({
      json: {
        ...state,
        stage: "working",
        revision: 2,
        workingAction: "revise",
      },
    });
  });
  await page.goto("/?mode=connected");
  const required = page.getByRole("textbox", { name: "優先条件", exact: true });
  const preferred = page.getByRole("textbox", {
    name: "希望条件",
    exact: true,
  });
  await expect(required).toHaveValue("電子レンジ対応, 3000円以下");
  await expect(preferred).toBeEditable();
  await expect(preferred).toHaveValue("");
  await expect(
    page.getByRole("textbox", { name: "否定条件", exact: true }),
  ).toBeEditable();
  await expect(
    page.getByRole("textbox", { name: "指定なし", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "条件", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("条件は半角カンマ（,）で区切ります。", { exact: false }),
  ).toBeVisible();
  const productBox = await page
    .getByRole("textbox", { name: "商品名", exact: true })
    .boundingBox();
  const requiredBox = await required.boundingBox();
  expect(productBox!.y + productBox!.height).toBeLessThan(requiredBox!.y);
  const status = page.getByTestId("reference-image-status");
  await expect(status).toHaveCount(0);
  await page.getByRole("switch").check();
  await expect(status).toHaveCount(0);
  await expect(page.getByRole("switch")).toBeChecked();
  await preferred.fill("軽い, 白");
  await page
    .getByRole("textbox", { name: "否定条件", exact: true })
    .fill("光沢");
  await expect(
    page.getByRole("button", { name: "参考画像を生成", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  expect(requests).toHaveLength(1);
  expect(requests[0]).toMatchObject({
    action: "revise",
    source:
      "マグカップ。電子レンジ対応。3000円以下。できれば軽い。できれば白。光沢は避けたい。",
  });
});

test("neutral conditions have no editor and survive edits to searchable conditions", async ({
  page,
}) => {
  const state = {
    stage: "query",
    revision: 1,
    editable: true,
    canRevise: true,
    input: "マグカップ。取っ手がなくてもよい。",
    productName: "マグカップ",
    conditionText: "取っ手がなくてもよい。",
    queries: ["マグカップ"],
    canSkipImages: true,
    canGenerateImages: false,
    conditionReview: [
      {
        start: 6,
        end: 16,
        quote: "取っ手がなくてもよい",
        target: "取っ手",
        strength: "neutral",
        reason: "permission",
      },
    ],
  };
  const commands: Record<string, unknown>[] = [];
  await page.route("**/api/state", (r) => r.fulfill({ json: state }));
  await page.route("**/api/command", (r) => {
    commands.push(r.request().postDataJSON());
    return r.fulfill({
      json: {
        ...state,
        stage: "working",
        revision: 2,
        workingAction: "revise",
      },
    });
  });
  await page.goto("/?mode=connected");
  await expect(
    page.getByRole("textbox", { name: "優先条件", exact: true }),
  ).toBeEditable();
  await expect(
    page.getByRole("textbox", { name: "指定なし", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("検索に使わない条件：取っ手", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "希望条件", exact: true })
    .fill("3000円以下");
  await page.getByRole("button", { name: "変更を反映", exact: true }).click();
  expect(commands).toHaveLength(1);
  expect(commands[0]).toMatchObject({
    action: "revise",
    source: "マグカップ。できれば3000円以下。取っ手がなくてもよい。",
  });
});

test("history headings use the searched product name instead of the original request", async ({
  page,
}) => {
  await page.route("**/api/state", (r) =>
    r.fulfill({
      json: {
        stage: "idle",
        revision: 0,
        historyOnly: true,
        historyAvailable: true,
      },
    }),
  );
  await page.route("**/api/history", (r) =>
    r.fulfill({
      json: {
        items: [
          {
            id: "h".repeat(43),
            summary: "3000円以下のマグカップを探しています。",
            productName: "マグカップ",
            completedAt: "2026-09-12T00:00:00Z",
            expiresAt: "2026-10-12T00:00:00Z",
            count: 1,
          },
        ],
      },
    }),
  );
  await page.goto("/?mode=connected#history");
  await expect(
    page.getByRole("heading", { name: "マグカップ", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("3000円以下のマグカップを探しています。", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "削除", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("マグカップ");
  await expect(page.getByRole("dialog")).not.toContainText("3000円以下");
});

test("search detail tabs align across unequal cards and stay put when toggled", async ({
  page,
}) => {
  await page.route("**/api/state", (r) =>
    r.fulfill({
      json: {
        stage: "complete",
        revision: 1,
        saved: true,
        products: [
          { ...product, title: "短い合成商品", reviewRating: 4.5 },
          {
            ...product,
            title:
              "長い商品名で複数行になる合成商品。丸い形と持ちやすさを確認するための表示用商品。",
            reviewRating: null,
          },
          { ...product, title: "画像のない合成商品", thumbnail: undefined },
        ].map((p) => ({
          ...p,
          titleEnStatus: "available",
          titleEn: "Synthetic product",
          scores: {
            title: { score_ja: 0.5, score_en: 0.8, score: 0.8 },
            conditions: [],
            image: 0.6,
          },
        })),
      },
    }),
  );
  await page.goto("/?mode=connected");
  await page.getByRole("button", { name: "結果を見る", exact: true }).click();
  const tabs = page.getByRole("list", { name: "検索結果" }).locator("summary");
  await expect(tabs).toHaveCount(3);
  await page.evaluate(() => document.fonts.ready);
  const positions = () =>
    tabs.evaluateAll((nodes) =>
      nodes.map((n) => n.getBoundingClientRect().top + window.scrollY),
    );
  const initial = await positions();
  expect(Math.max(...initial) - Math.min(...initial)).toBeLessThan(1);
  for (const index of [0, 1, 0, 1]) {
    await tabs.nth(index).click();
    const current = await positions();
    current.forEach((value, i) =>
      expect(Math.abs(value - initial[i])).toBeLessThan(1),
    );
  }
});

test("editable image prompts regenerate comparisons and final shows product name", async ({
  page,
}) => {
  const png =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3e8AAAAASUVORK5CYII=";
  let view = {
    stage: "reference",
    revision: 1,
    productName: "合成の商品",
    selectedQuery: "合成の商品 検索語",
    images: [png],
    canSkipImages: true,
    canRegenerate: true,
    canRegenerateComparisons: false,
    referenceRemaining: 1,
    imagePrompts: {
      reference: "Original reference.",
      comparison: { "visual-condition-001": "Original comparison." },
    },
    conditionLabels: { "visual-condition-001": "表面" },
  };
  const commands: {
    action: string;
    prompt?: string;
    prompts?: Record<string, string>;
  }[] = [];
  await page.route("**/api/state", (route) => route.fulfill({ json: view }));
  await page.route("**/api/command", async (route) => {
    const body = route.request().postDataJSON();
    commands.push(body);
    if (
      body.action === "comparison" ||
      body.action === "regenerate_comparisons"
    ) {
      view = {
        ...view,
        stage: "comparison",
        revision: view.revision + 2,
        images: [png, png],
        imagePrompts: { ...view.imagePrompts, comparison: body.prompts },
        canRegenerateComparisons: body.action === "comparison",
        canRegenerate: body.action === "comparison",
        referenceRemaining: body.action === "comparison" ? 1 : 0,
      };
    } else if (body.action === "final")
      view = { ...view, stage: "final", revision: view.revision + 2 };
    await route.fulfill({ json: view });
  });
  await page.goto("/?mode=connected");
  await page
    .getByRole("textbox", { name: "参考画像のプロンプト", exact: true })
    .fill("Changed reference.");
  await expect(
    page.getByRole("button", { name: "了承して生成", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("textbox", { name: "参考画像のプロンプト", exact: true })
    .fill("Original reference.");
  await page
    .getByRole("textbox", { name: "比較画像のプロンプト：表面", exact: true })
    .fill("First comparison edit.");
  await page.getByRole("button", { name: "了承して生成", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("textbox", { name: "比較画像のプロンプト：表面", exact: true })
    .fill("Second comparison edit.");
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "比較画像を再生成", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "作り直す", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "最終確認へ", exact: true }),
  ).toBeEnabled();
  expect(commands.map((c) => c.action)).toEqual([
    "comparison",
    "regenerate_comparisons",
  ]);
  expect(commands[1].prompts).toEqual({
    "visual-condition-001": "Second comparison edit.",
  });
  await page.getByRole("button", { name: "最終確認へ", exact: true }).click();
  await expect(page.getByTestId("final-product-name")).toHaveText("合成の商品");
  await expect(page.getByTestId("final-product-name")).toHaveCSS(
    "background-color",
    "rgb(33, 33, 33)",
  );
  await expect(page.getByText("検索語を確認", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("この確認で商品検索を1回実行します。", { exact: true }),
  ).toHaveCount(0);
});

for (const action of ["final", "without_images"]) {
  test(`working ${action} stays on final confirmation without a research flash`, async ({
    page,
  }) => {
    await page.route("**/api/state", (route) =>
      route.fulfill({
        json: {
          stage: "working",
          workingAction: action,
          revision: 3,
          productName: "合成商品",
          imageMode: "off",
          images: [],
          conditions: [],
        },
      }),
    );
    await page.goto("/?mode=connected");
    await expect(
      page.getByRole("heading", { name: "検索内容を最終確認", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("list", { name: "商品調査の進行" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "検索", exact: true }),
    ).toBeDisabled();
  });
}
