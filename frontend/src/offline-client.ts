import type { SearchView, SearchStage } from "./connected-api";
import type { SearchClient } from "./search-client";
import type { HistoryDetail } from "./connected-history-api";
import { HISTORY_TTL_MS, type HistoryStorage } from "./history";
import { PRODUCTS } from "./model";
import { mockProducts, offlineHistory } from "./offline-history";

const IMAGES = [
  "/images/keyboard-white.svg",
  "/images/keyboard-dark.svg",
  "/images/keyboard-full.svg",
];
const APPROVAL_MS = 15 * 60_000;
const PREPARATIONS = 3;
const IMAGE_SETS = 2;
const DEFAULT_TERMS =
  "ワイヤレス接続。コンパクトなサイズ。15000円以下。できれば白い本体。できれば静かな打鍵音。テンキー付きは避けたい。";

function conditionRows(
  source: string,
): NonNullable<SearchView["conditionReview"]> {
  return [...source.matchAll(/[^。]+/g)].map((match) => {
    const quote = match[0];
    const strength = quote.startsWith("できれば")
      ? "preferred"
      : quote.endsWith("は避けたい")
        ? "excluded"
        : quote.endsWith("にはこだわらない")
          ? "neutral"
          : "required";
    const target = quote
      .replace(/^できれば/, "")
      .replace(/は避けたい$|にはこだわらない$/, "");
    const start = Array.from(source.slice(0, match.index)).length;
    return {
      start,
      end: start + Array.from(quote).length,
      quote,
      target,
      strength,
      reason: "explicit_condition",
    };
  });
}

export function createOfflineClient(
  storage: () => HistoryStorage,
  scenario = "default",
): SearchClient {
  let view: SearchView = idle(0);
  let preparations = 0;
  let sets = 0;
  let due = 0;
  let finish: (() => void) | null = null;
  let savedEntry: HistoryDetail | null = null;
  const failures = new Set<string>();
  let cleanupPending = false;
  let cleanedAt = 0;
  function cleanup() {
    cleanedAt = Date.now();
    try {
      offlineHistory(storage()).purge();
      cleanupPending = false;
    } catch {
      cleanupPending = true;
    }
  }
  function idle(revision: number): SearchView {
    return {
      stage: "idle",
      revision,
      mode: "fixture",
      editable: true,
      canReset: true,
      historyAvailable: true,
      images: [],
    };
  }
  function failOnce(name: string) {
    if (scenario !== name || failures.has(name)) {
      return false;
    }
    failures.add(name);
    return true;
  }
  function update(patch: Partial<SearchView>) {
    view = { ...view, ...patch, revision: view.revision + 1 };
  }
  function ready(stage: SearchStage) {
    update({
      stage,
      workingAction: undefined,
      canCancel: false,
      canReset: true,
      canRevise:
        preparations < PREPARATIONS &&
        stage !== "complete" &&
        stage !== "attributes",
    });
  }
  function work(action: string, callback: () => void, delay = 900) {
    update({
      stage: "working",
      workingAction: action,
      canReset: false,
      canRevise: false,
      canCancel: action === "search",
    });
    due = Date.now() + delay;
    finish = callback;
  }
  function snapshot() {
    if (Date.now() - cleanedAt >= 60_000) {
      cleanup();
    }
    if (finish && Date.now() >= due) {
      const callback = finish;
      finish = null;
      callback();
    }
    if (
      view.expiresAt &&
      Date.now() >= Date.parse(view.expiresAt) &&
      ["query", "reference", "comparison", "final"].includes(view.stage)
    ) {
      ready("expired");
      update({
        message:
          "確認の期限が切れました。画像なしで続けるか、条件を整理し直してください。",
      });
    }
    return structuredClone(view);
  }
  function persist() {
    try {
      if (!savedEntry) {
        const now = Date.now();
        savedEntry = {
          id:
            crypto.randomUUID().replaceAll("-", "") +
            crypto.randomUUID().replaceAll("-", ""),
          summary: view.input ?? "合成検索",
          productName: view.productName,
          completedAt: new Date(now).toISOString(),
          expiresAt: new Date(now + HISTORY_TTL_MS).toISOString(),
          count: view.products?.length ?? 0,
          view: {
            ...structuredClone(view),
            saved: true,
            canRetrySave: false,
            message: undefined,
          },
        };
      }
      if (failOnce("save-error")) {
        throw new Error("Synthetic save failure");
      }
      offlineHistory(storage()).save(savedEntry);
      update({ saved: true, canRetrySave: false, message: undefined });
    } catch {
      update({
        saved: false,
        canRetrySave: true,
        message:
          "結果を履歴に保存できませんでした。結果はこの画面で確認できます。",
      });
    }
  }
  function complete() {
    const products = mockProducts(
      scenario === "empty" ? [] : PRODUCTS,
      view.imageMode !== "off",
    )!;
    update({
      products: products.map((product, index) => ({
        ...product,
        scores: {
          title: {
            score_ja: 1 - index * 0.03,
            score_en: null,
            score: 1 - index * 0.03,
          },
          ...(view.imageMode === "off"
            ? {}
            : { textImage: 0.95 - index * 0.025 }),
          image: view.imageMode === "off" ? null : 0.9 - index * 0.02,
          conditions: (view.conditionReview ?? [])
            .filter((r) => r.strength !== "neutral")
            .map((row, i) => ({
              requirement_id: `condition-${i}`,
              weight: new Set(
                (view.conditionReview ?? [])
                  .filter(
                    (other) =>
                      other.strength === row.strength &&
                      other.start >= row.start,
                  )
                  .map((other) => other.start),
              ).size,
              strength: row.strength as "required" | "preferred" | "excluded",
              score_ja: row.strength === "excluded" ? index / 20 : 0.7,
              score_en: row.strength === "excluded" ? index / 20 : 0.8,
              score: row.strength === "excluded" ? index / 20 : 0.8,
            })),
        },
      })),
      researchStep: 5,
      historyContentAvailable: true,
      sortProfile:
        view.imageMode === "off"
          ? "excluded-title-conditions-image-review-v1"
          : "excluded-title-conditions-text-image-review-v2",
      expiresAt: undefined,
    });
    ready("complete");
    persist();
  }
  function research() {
    if (view.cancelRequested) {
      ready("cancelled");
      update({
        message: "検索を中止しました。",
        canSkipImages: false,
        expiresAt: undefined,
      });
      return;
    }
    if (failOnce("research-error")) {
      ready("failed");
      update({
        message: "商品を取得できませんでした。条件を整理し直してください。",
      });
      return;
    }
    const step = (view.researchStep ?? 0) + 1;
    update({ researchStep: step, canCancel: step < 2 });
    if (step === 2 && scenario === "attributes") {
      ready("attributes");
      update({
        unresolved: ["connection"],
        options: [
          {
            id: "wireless",
            label: "ワイヤレス接続",
            conditions: ["connection"],
          },
        ],
      });
    } else if (step < 5) {
      due = Date.now() + 1100;
      finish = research;
    } else {
      complete();
    }
  }
  async function sendSearch(
    action: string,
    previous: SearchView,
    values: object = {},
  ) {
    snapshot();
    if (previous.revision !== view.revision) {
      return snapshot();
    }
    const data = values as {
      source?: string;
      imageMode?: string;
      prompt?: string;
      prompts?: Record<string, string>;
      selections?: Record<string, string>;
    };
    if (action === "cancel" && view.canCancel) {
      update({ cancelRequested: true, canCancel: false });
      return snapshot();
    }
    if (view.stage === "working") {
      return snapshot();
    }
    if (action === "reset" && view.canReset) {
      view = idle(view.revision + 1);
      preparations = 0;
      sets = 0;
      savedEntry = null;
      finish = null;
    } else if (
      (action === "start" && view.stage === "idle") ||
      (action === "revise" && view.canRevise)
    ) {
      const source = data.source?.trim() ?? "";
      if (
        !source ||
        Array.from(source).length > 2000 ||
        preparations >= PREPARATIONS
      ) {
        return snapshot();
      }
      const revised = action === "revise" && source !== view.input;
      const separator = source.indexOf("。");
      const productName =
        revised && separator > 0 && separator <= 100
          ? source.slice(0, separator)
          : ((action === "revise" ? view.productName : undefined) ??
            "メカニカルキーボード");
      const terms =
        revised && separator > 0
          ? source.slice(separator + 1)
          : ((action === "revise" ? view.conditionText : undefined) ??
            DEFAULT_TERMS);
      preparations += 1;
      sets = 0;
      view = {
        ...idle(view.revision + 1),
        input: data.source,
        productName,
        conditionText: terms,
        conditionReview: conditionRows(terms),
        imageMode: data.imageMode === "on" ? undefined : "off",
        images: [],
      };
      work(action, () => {
        if (failOnce("organize-error")) {
          ready("failed");
          update({
            message:
              "条件を整理できませんでした。文章を修正するか再試行してください。",
          });
          return;
        }
        const rows = view.conditionReview ?? [];
        ready(
          scenario === "clarification" && preparations === 1
            ? "clarification"
            : "query",
        );
        update({
          queries: [productName],
          selectedQuery: productName,
          conditions:
            scenario === "no-appearance"
              ? []
              : ["白い本体", "コンパクトなサイズ"],
          conditionLabels: {
            ...Object.fromEntries(
              rows
                .filter((r) => r.strength !== "neutral")
                .map((r, i) => [`condition-${i}`, r.target]),
            ),
            color: "色",
            shape: "形",
          },
          canSkipImages: true,
          canGenerateImages:
            view.imageMode !== "off" && scenario !== "no-appearance",
          referenceRemaining: IMAGE_SETS,
          imagePrompts:
            view.imageMode === "off"
              ? null
              : {
                  reference: "A white compact keyboard on a plain background.",
                  comparison: {
                    color: "Change only the white body to black.",
                    shape:
                      "Change only the compact keyboard to a full-size keyboard.",
                  },
                },
          expiresAt: new Date(Date.now() + APPROVAL_MS).toISOString(),
          message:
            view.stage === "clarification"
              ? "合成シナリオ：文章を修正してください。"
              : undefined,
        });
      });
    } else if (action === "without_images" && view.canSkipImages) {
      update({
        imageMode: "off",
        images: [],
        imagePrompts: null,
        canRegenerate: false,
        canRegenerateComparisons: false,
        canSkipImages: false,
        expiresAt: new Date(Date.now() + APPROVAL_MS).toISOString(),
      });
      ready("final");
    } else if (
      (action === "reference" &&
        view.stage === "query" &&
        view.canGenerateImages) ||
      (action === "regenerate" && view.canRegenerate) ||
      (action === "regenerate_comparisons" && view.canRegenerateComparisons)
    ) {
      if (sets >= IMAGE_SETS || view.imageMode === "off") {
        return snapshot();
      }
      sets += 1;
      const comparison = action === "regenerate_comparisons";
      update({
        images: comparison ? view.images?.slice(0, 1) : [],
        expiresAt: undefined,
        referenceRemaining: IMAGE_SETS - sets,
        canRegenerate: false,
        canRegenerateComparisons: false,
        imagePrompts: {
          reference: data.prompt ?? view.imagePrompts!.reference,
          comparison: data.prompts ?? view.imagePrompts!.comparison,
        },
      });
      work(
        action,
        () => {
          const failed = failOnce(
            comparison ? "comparison-error" : "reference-error",
          );
          ready(failed ? "failed" : comparison ? "comparison" : "reference");
          update({
            images: failed ? view.images : comparison ? IMAGES : [IMAGES[0]],
            canSkipImages: true,
            canRegenerate: sets < IMAGE_SETS,
            canRegenerateComparisons: comparison && sets < IMAGE_SETS,
            message: failed
              ? "画像の準備に失敗しました。作り直すか画像なしで続けられます。"
              : undefined,
            expiresAt: new Date(Date.now() + APPROVAL_MS).toISOString(),
          });
        },
        2400,
      );
    } else if (action === "comparison" && view.stage === "reference") {
      update({
        imagePrompts: {
          reference: view.imagePrompts!.reference,
          comparison: data.prompts ?? view.imagePrompts!.comparison,
        },
        expiresAt: undefined,
      });
      work(
        action,
        () => {
          const failed = failOnce("comparison-error");
          ready(failed ? "failed" : "comparison");
          update({
            images: failed ? [IMAGES[0]] : IMAGES,
            canRegenerateComparisons: sets < IMAGE_SETS,
            message: failed ? "比較画像の準備に失敗しました。" : undefined,
            expiresAt: new Date(Date.now() + APPROVAL_MS).toISOString(),
          });
        },
        2400,
      );
    } else if (action === "final" && view.stage === "comparison") {
      ready("final");
    } else if (action === "search" && view.stage === "final") {
      update({
        researchStep: 0,
        canSkipImages: false,
        canRegenerate: false,
        canRegenerateComparisons: false,
        expiresAt: undefined,
      });
      work(action, research, 1100);
    } else if (
      action === "rank" &&
      view.stage === "attributes" &&
      data.selections?.connection === "wireless"
    ) {
      work(action, research, 1100);
    } else if (action === "retry_save" && view.canRetrySave) {
      persist();
    }
    return snapshot();
  }
  return {
    offline: true,
    readSearch: async () => snapshot(),
    sendSearch,
    readHistoryState: async () => {
      cleanup();
      return { items: offlineHistory(storage()).all(), cleanupPending };
    },
    readHistoryDetail: async (id) => offlineHistory(storage()).detail(id),
    deleteHistory: async (id) => {
      if (failOnce("delete-error")) {
        throw new Error("Synthetic delete failure");
      }
      offlineHistory(storage()).remove(id);
    },
    purgeExpiredHistory: async () => offlineHistory(storage()).purge(),
  };
}
