import { parseSearchView, type SearchView } from "./connected-api";
import {
  HistoryUnavailable,
  type HistoryDetail,
} from "./connected-history-api";
import {
  readHistory,
  deleteHistory,
  HISTORY_TTL_MS,
  type HistoryStorage,
} from "./history";
import { type Product } from "./model";

export const OFFLINE_HISTORY_KEY = "amazon-explorer.mock-history.v2";
const IMAGES = [
  "/images/keyboard-white.svg",
  "/images/keyboard-dark.svg",
  "/images/keyboard-full.svg",
];
const PNG = "data:image/png;base64,AA==";

export function mockProducts(
  products: Product[],
  useImages: boolean,
): SearchView["products"] {
  return products.map((product, index) => ({
    title: product.name,
    titleEn: index % 3 === 0 ? null : `Synthetic keyboard ${index + 1}`,
    titleEnStatus: index % 3 === 0 ? "unavailable" : "available",
    price: product.price,
    url: null,
    required: product.mismatched.length ? "不一致" : "未確認",
    appearance: useImages ? "合成画像の比較例" : "未使用",
    thumbnail: product.image,
    reviewRating: product.rating,
  }));
}

function validate(entry: HistoryDetail): HistoryDetail {
  if (
    !entry ||
    typeof entry.id !== "string" ||
    !entry.id ||
    typeof entry.summary !== "string" ||
    Array.from(entry.summary).length > 2000 ||
    !Number.isFinite(Date.parse(entry.completedAt)) ||
    !Number.isFinite(Date.parse(entry.expiresAt)) ||
    Date.parse(entry.expiresAt) - Date.parse(entry.completedAt) !==
      HISTORY_TTL_MS ||
    entry.view?.stage !== "complete" ||
    !entry.view.saved ||
    entry.count !== entry.view.products?.length ||
    entry.view.products?.some(
      (p) =>
        p.url !== null ||
        (p.thumbnail != null && !IMAGES.includes(p.thumbnail)),
    ) ||
    entry.view.images?.some((src) => !IMAGES.includes(src))
  ) {
    throw new Error("Invalid offline history");
  }
  // Validate shared fields without allowing stored URLs to cause network requests.
  // Mock condition rows are synthetic, not an interpretation of the user's input.
  parseSearchView(
    {
      ...entry.view,
      historyContentAvailable: false,
      images: entry.view.images?.map(() => PNG),
      products: entry.view.products?.map((p) => ({
        ...p,
        thumbnail: p.thumbnail ? PNG : null,
      })),
    },
    48,
  );
  return entry;
}

export function offlineHistory(storage: HistoryStorage) {
  function load(): HistoryDetail[] {
    const raw = storage.getItem(OFFLINE_HISTORY_KEY);
    if (raw === null) {
      return [];
    }
    const entries: unknown = JSON.parse(raw);
    if (!Array.isArray(entries) || entries.length > 30) {
      throw new Error("Invalid offline history");
    }
    const result = entries.map(validate);
    if (new Set(result.map((e) => e.id)).size !== result.length) {
      throw new Error("Duplicate offline history");
    }
    return result;
  }
  function current() {
    return load().filter((e) => Date.parse(e.expiresAt) > Date.now());
  }
  function all() {
    const legacy = readHistory(storage, Date.now()).map((entry) => ({
      id: `legacy-${entry.id}`,
      summary: entry.input,
      productName: entry.conditions.product,
      completedAt: new Date(entry.createdAt).toISOString(),
      expiresAt: new Date(entry.createdAt + HISTORY_TTL_MS).toISOString(),
      count: entry.products.length,
      view: {
        stage: "complete",
        revision: 0,
        mode: "fixture",
        saved: true,
        input: entry.input,
        productName: entry.conditions.product,
        imageMode: entry.useImages ? undefined : "off",
        images: entry.useImages ? IMAGES : [],
        conditionLabels: {
          required: entry.conditions.required,
          preferred: entry.conditions.preferred,
          excluded: entry.conditions.excluded,
          budget: entry.conditions.budget,
        },
        products: mockProducts(entry.products, entry.useImages),
      } as SearchView,
    }));
    return [...current(), ...legacy]
      .sort((a, b) => Date.parse(b.completedAt) - Date.parse(a.completedAt))
      .slice(0, 30);
  }
  return {
    all,
    save(entry: HistoryDetail) {
      validate(entry);
      storage.setItem(
        OFFLINE_HISTORY_KEY,
        JSON.stringify(
          [entry, ...current().filter((e) => e.id !== entry.id)].slice(0, 30),
        ),
      );
    },
    detail(id: string) {
      const entry = all().find((e) => e.id === id);
      if (!entry) {
        throw new HistoryUnavailable();
      }
      return entry;
    },
    remove(id: string) {
      if (id.startsWith("legacy-")) {
        deleteHistory(storage, id.slice(7), Date.now());
      } else {
        storage.setItem(
          OFFLINE_HISTORY_KEY,
          JSON.stringify(current().filter((e) => e.id !== id)),
        );
      }
    },
    purge() {
      const entries = load();
      const retained = entries.filter(
        (e) => Date.parse(e.expiresAt) > Date.now(),
      );
      if (retained.length !== entries.length) {
        storage.setItem(OFFLINE_HISTORY_KEY, JSON.stringify(retained));
      }
      readHistory(storage, Date.now());
    },
  };
}
