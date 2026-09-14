import type { ImagePrompts } from "./image-prompt-values";
import {
  ConnectionError,
  CONNECTION_TIMEOUT_MS,
  validationReason,
  type ConnectionOperation,
} from "./connection-diagnostics";
const STAGES = [
  "idle",
  "working",
  "query",
  "clarification",
  "reference",
  "comparison",
  "final",
  "attributes",
  "complete",
  "failed",
  "expired",
  "cancelled",
] as const;
export type SearchStage = (typeof STAGES)[number];
export interface LanguageScore {
  score_ja: number;
  score_en: number | null;
  score: number;
}
export interface ProductScores {
  title: LanguageScore;
  image?: number | null;
  textImage?: number | null;
  total?: number;
  conditions: (LanguageScore & {
    requirement_id: string;
    strength: "required" | "preferred" | "excluded";
    weight?: number;
  })[];
}
export interface SearchView {
  imagePrompts?: ImagePrompts | null;
  canRegenerateComparisons?: boolean;
  workingAction?: string;
  referenceRemaining?: number;
  researchStep?: number;
  canReset?: boolean;
  canRegenerate?: boolean;
  canRetrySave?: boolean;
  canCancel?: boolean;
  cancelRequested?: boolean;
  imageMode?: "off";
  canSkipImages?: boolean;
  canGenerateImages?: boolean;
  stage: SearchStage;
  revision: number;
  instanceId?: string;
  mode?: "fixture" | "live";
  input?: string;
  editable?: boolean;
  canRevise?: boolean;
  historyAvailable?: boolean;
  historyOnly?: boolean;
  historyContentAvailable?: boolean;
  sortProfile?:
    | "title-image-conditions-v1"
    | "excluded-title-conditions-image-review-v1"
    | "excluded-title-conditions-text-image-review-v2"
    | null;
  conditionLabels?: Record<string, string>;
  productName?: string;
  conditionText?: string;
  queries?: string[];
  selectedQuery?: string;
  conditions?: string[];
  conditionReview?: {
    start: number;
    end: number;
    quote: string;
    target: string;
    strength: "required" | "preferred" | "excluded" | "neutral";
    reason: string;
  }[];
  conditionIssues?: {
    start: number;
    end: number;
    quote: string;
    code: string;
  }[];
  images?: string[];
  expiresAt?: string;
  message?: string;
  saved?: boolean;
  unresolved?: string[];
  options?: { id: string; label: string; conditions: string[] }[];
  products?: {
    title: string;
    titleEn?: string | null;
    titleEnStatus?: "available" | "unavailable";
    price: number | null;
    url: string | null;
    required: string;
    appearance: string;
    thumbnail?: string | null;
    reviewRating?: number | null;
    scores?: ProductScores;
  }[];
}

function unit(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 1
  );
}

function languageScore(value: unknown): value is LanguageScore {
  if (!value || typeof value !== "object") return false;
  const row = value as LanguageScore;
  return (
    unit(row.score_ja) &&
    (row.score_en === null || unit(row.score_en)) &&
    unit(row.score) &&
    row.score === Math.max(row.score_ja, row.score_en ?? 0)
  );
}

function productScores(value: unknown): value is ProductScores {
  if (!value || typeof value !== "object") return false;
  const scores = value as ProductScores;
  return (
    languageScore(scores.title) &&
    (scores.image === undefined ||
      scores.image === null ||
      unit(scores.image)) &&
    (scores.textImage === undefined ||
      scores.textImage === null ||
      unit(scores.textImage)) &&
    (scores.total === undefined || unit(scores.total)) &&
    Array.isArray(scores.conditions) &&
    scores.conditions.length <= 32 &&
    scores.conditions.every(
      (row) =>
        languageScore(row) &&
        typeof row.requirement_id === "string" &&
        row.requirement_id.length <= 100 &&
        (row.weight === undefined ||
          (Number.isInteger(row.weight) &&
            row.weight >= 1 &&
            row.weight <= 64)) &&
        ["required", "preferred", "excluded"].includes(row.strength),
    )
  );
}

function png(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 4_000_000 &&
    /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(value)
  );
}

function strings(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= 24 &&
    value.every((item) => typeof item === "string" && item.length <= 4_000_000)
  );
}

export function parseSearchView(
  value: unknown,
  maximumProducts: 24 | 48 = 24,
): SearchView {
  if (typeof value !== "object" || value === null) {
    throw new Error("Invalid search response");
  }
  const data = value as Record<string, unknown>;
  if (
    data.sortProfile !== undefined &&
    data.sortProfile !== null &&
    ![
      "title-image-conditions-v1",
      "excluded-title-conditions-image-review-v1",
      "excluded-title-conditions-text-image-review-v2",
    ].includes(data.sortProfile as string)
  )
    throw new Error("Invalid ranking profile");
  for (const [key, maximum] of [
    ["productName", 100],
    ["conditionText", 2000],
  ] as const) {
    const value = data[key];
    if (
      value !== undefined &&
      (typeof value !== "string" ||
        Array.from(value).length > maximum ||
        (key === "productName" && !value.trim()))
    )
      throw new Error("Invalid editable terms");
  }
  for (const key of [
    "canSkipImages",
    "canGenerateImages",
    "editable",
    "canRevise",
    "historyAvailable",
    "historyOnly",
    "historyContentAvailable",
    "canReset",
    "canRegenerate",
    "canRegenerateComparisons",
    "canRetrySave",
    "canCancel",
    "cancelRequested",
  ]) {
    if (data[key] !== undefined && typeof data[key] !== "boolean")
      throw new Error("Invalid editing state");
  }
  if (
    data.conditionLabels !== undefined &&
    (!data.conditionLabels ||
      typeof data.conditionLabels !== "object" ||
      Array.isArray(data.conditionLabels) ||
      Object.keys(data.conditionLabels).length > 32 ||
      !Object.values(data.conditionLabels).every(
        (value) => typeof value === "string" && value.length <= 2000,
      ))
  )
    throw new Error("Invalid condition labels");
  for (const key of ["conditionReview", "conditionIssues"]) {
    const rows = data[key];
    if (rows === undefined) continue;
    if (
      !Array.isArray(rows) ||
      rows.length > 24 ||
      !rows.every((row) => {
        if (
          !row ||
          !Number.isInteger(row.start) ||
          !Number.isInteger(row.end) ||
          row.start < 0 ||
          row.end <= row.start ||
          row.end > 2000 ||
          typeof row.quote !== "string" ||
          row.quote.length > 2000
        )
          return false;
        if (key === "conditionIssues")
          return [
            "ambiguous_negation",
            "condition_count",
            "conflicting_modifiers",
            "conflicting_conditions",
            "modifier_scope",
          ].includes(row.code);
        return (
          typeof row.target === "string" &&
          row.target.length > 0 &&
          row.target.length <= 2000 &&
          ["required", "preferred", "excluded", "neutral"].includes(
            row.strength,
          ) &&
          [
            "explicit_condition",
            "permission",
            "avoidance",
            "preference_suffix",
            "requirement_suffix",
            "preference_prefix",
            "requirement_prefix",
          ].includes(row.reason)
        );
      })
    )
      throw new Error("Invalid condition interpretation");
  }
  if (
    data.historyContentAvailable === true &&
    (typeof data.input !== "string" ||
      Array.from(data.input).length === 0 ||
      Array.from(data.input).length > 2000 ||
      data.conditionLabels === undefined ||
      !Array.isArray(data.conditionReview) ||
      !data.conditionReview.every(
        (row) =>
          Array.from(data.input as string)
            .slice(row.start, row.end)
            .join("") === row.quote,
      ))
  )
    throw new Error("Invalid saved history content");
  for (const [key, maximum] of [
    ["referenceRemaining", 2],
    ["researchStep", 5],
  ] as const) {
    if (
      data[key] !== undefined &&
      (!Number.isInteger(data[key]) ||
        (data[key] as number) < 0 ||
        (data[key] as number) > maximum)
    )
      throw new Error("Invalid progress");
  }
  if (
    data.workingAction !== undefined &&
    ![
      "start",
      "revise",
      "reset",
      "reference",
      "regenerate",
      "regenerate_comparisons",
      "comparison",
      "final",
      "without_images",
      "search",
      "rank",
      "retry_save",
    ].includes(data.workingAction as string)
  )
    throw new Error("Invalid operation");
  if (data.imagePrompts != null) {
    const prompts = data.imagePrompts as ImagePrompts;
    const bounded = (value: unknown) =>
      typeof value === "string" &&
      value.length > 0 &&
      Array.from(value).length <= 12000;
    if (
      !bounded(prompts.reference) ||
      !prompts.comparison ||
      typeof prompts.comparison !== "object" ||
      Array.isArray(prompts.comparison) ||
      Object.keys(prompts.comparison).length > 3 ||
      !Object.values(prompts.comparison).every(bounded)
    )
      throw new Error("Invalid image prompts");
  }
  if (data.imageMode !== undefined && data.imageMode !== "off")
    throw new Error("Invalid image mode");
  if (
    data.imageMode === "off" &&
    (!Array.isArray(data.images) ||
      data.images.length !== 0 ||
      ["reference", "comparison"].includes(data.stage as string))
  )
    throw new Error("Image-free search contains image evidence");
  const requiredList =
    data.stage === "query"
      ? "queries"
      : ["reference", "comparison", "final"].includes(data.stage as string) &&
          data.imageMode !== "off"
        ? "images"
        : data.stage === "complete"
          ? "products"
          : null;
  if (
    requiredList &&
    (!Array.isArray(data[requiredList]) ||
      ((data[requiredList] as unknown[]).length === 0 &&
        !(requiredList === "products" && data.imageMode === "off")))
  ) {
    throw new Error("Missing search content");
  }
  if (
    !STAGES.includes(data.stage as SearchStage) ||
    !Number.isInteger(data.revision) ||
    (data.revision as number) < 0
  ) {
    throw new Error("Invalid search state");
  }
  if (
    data.instanceId !== undefined &&
    (typeof data.instanceId !== "string" ||
      !/^[0-9a-f]{32}$/.test(data.instanceId))
  ) {
    throw new Error("Invalid server instance");
  }
  for (const field of ["queries", "conditions", "images", "unresolved"]) {
    if (data[field] !== undefined && !strings(data[field])) {
      throw new Error("Invalid search list");
    }
  }
  for (const field of ["input", "selectedQuery", "message", "expiresAt"]) {
    if (data[field] !== undefined && typeof data[field] !== "string") {
      throw new Error("Invalid search text");
    }
  }
  if (data.images && !(data.images as string[]).every(png)) {
    throw new Error("Invalid preview source");
  }
  if (
    data.options !== undefined &&
    (!Array.isArray(data.options) ||
      !data.options.every(
        (option) =>
          option &&
          typeof option.id === "string" &&
          typeof option.label === "string" &&
          strings(option.conditions),
      ))
  ) {
    throw new Error("Invalid condition options");
  }
  if (
    data.products !== undefined &&
    (!Array.isArray(data.products) ||
      data.products.length > maximumProducts ||
      !data.products.every((product) => {
        if (
          data.imageMode === "off" &&
          (product?.scores?.image != null || product?.scores?.textImage != null)
        )
          return false;
        if (
          product?.reviewRating !== undefined &&
          product.reviewRating !== null &&
          (typeof product.reviewRating !== "number" ||
            !Number.isFinite(product.reviewRating) ||
            product.reviewRating < 0 ||
            product.reviewRating > 5)
        )
          return false;
        if (
          (product?.thumbnail !== undefined &&
            product.thumbnail !== null &&
            !png(product.thumbnail)) ||
          (product?.scores !== undefined && !productScores(product.scores))
        )
          return false;
        if (
          !product ||
          typeof product.title !== "string" ||
          !["一致", "未確認", "不一致"].includes(product.required) ||
          typeof product.appearance !== "string"
        ) {
          return false;
        }
        if (
          (product.titleEnStatus === undefined &&
            product.titleEn !== undefined) ||
          (product.titleEnStatus !== undefined &&
            !["available", "unavailable"].includes(product.titleEnStatus)) ||
          (product.titleEnStatus === "available" &&
            (typeof product.titleEn !== "string" ||
              !product.titleEn.trim() ||
              product.titleEn.length > 500)) ||
          (product.titleEnStatus === "unavailable" && product.titleEn !== null)
        ) {
          return false;
        }
        if (
          product.price !== null &&
          (!Number.isInteger(product.price) || product.price <= 0)
        ) {
          return false;
        }
        if (product.url === null) {
          return true;
        }
        try {
          const url = new URL(product.url);
          return (
            url.protocol === "https:" &&
            !url.username &&
            !url.password &&
            !url.port &&
            (url.hostname === "amazon.co.jp" ||
              url.hostname.endsWith(".amazon.co.jp"))
          );
        } catch {
          return false;
        }
      }))
  ) {
    throw new Error("Invalid search products");
  }
  const view = data as unknown as SearchView;
  // A running older server cannot be restarted without losing its approved plan.
  // Recover only an explicit first product clause already present in its query.
  if (
    view.stage === "query" &&
    view.productName === undefined &&
    view.input &&
    view.queries?.[0]
  ) {
    const separator = view.input.indexOf("。");
    const productName = (
      separator < 0 ? view.input : view.input.slice(0, separator)
    ).trim();
    const normalize = (value: string) =>
      value.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
    const name = normalize(productName);
    const query = normalize(view.queries[0]);
    const source = Array.from(view.input);
    const prefixLength = Array.from(
      separator < 0 ? view.input : view.input.slice(0, separator + 1),
    ).length;
    if (
      name &&
      Array.from(productName).length <= 100 &&
      !/[\n\r]/.test(productName) &&
      (query === name || query.startsWith(name + " ")) &&
      (view.conditionReview ?? []).every(
        (row) =>
          row.start >= prefixLength &&
          source.slice(row.start, row.end).join("") === row.quote,
      )
    ) {
      return {
        ...view,
        productName,
        conditionText: separator < 0 ? "" : view.input.slice(separator + 1),
      };
    }
  }
  return view;
}

async function searchRequest(
  operation: ConnectionOperation,
  init: RequestInit,
): Promise<SearchView> {
  const started = performance.now();
  const signal = AbortSignal.timeout(CONNECTION_TIMEOUT_MS);
  const transportCode = () =>
    signal.aborted
      ? signal.reason?.name === "TimeoutError"
        ? "timeout"
        : "aborted"
      : "network";
  let response: Response;
  try {
    response = await fetch(
      operation === "state" ? "/api/state" : "/api/command",
      { ...init, signal },
    );
  } catch {
    throw new ConnectionError(
      transportCode(),
      operation,
      performance.now() - started,
    );
  }
  if (!response.ok) {
    throw new ConnectionError(
      "http",
      operation,
      performance.now() - started,
      response.status,
    );
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch (error) {
    throw new ConnectionError(
      signal.aborted
        ? transportCode()
        : error instanceof SyntaxError
          ? "json"
          : "network",
      operation,
      performance.now() - started,
      response.status,
    );
  }
  try {
    return parseSearchView(value);
  } catch (error) {
    throw new ConnectionError(
      "schema",
      operation,
      performance.now() - started,
      response.status,
      validationReason(error),
    );
  }
}

export async function readSearch(): Promise<SearchView> {
  return searchRequest("state", { cache: "no-store" });
}

export async function sendSearch(
  action: string,
  view: SearchView,
  values: object = {},
): Promise<SearchView> {
  return searchRequest("command", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Amazon-Explorer-Browser": "1",
    },
    body: JSON.stringify({
      action,
      revision: view.revision,
      operation: crypto.randomUUID(),
      ...values,
      ...(view.instanceId === undefined ? {} : { instanceId: view.instanceId }),
    }),
  });
}
