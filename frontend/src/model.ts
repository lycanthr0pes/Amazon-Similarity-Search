export type Screen =
  | "input"
  | "organizing"
  | "review"
  | "referenceGenerating"
  | "referenceReview"
  | "comparisonGenerating"
  | "comparisonReview"
  | "final"
  | "research"
  | "complete"
  | "results";

export interface Conditions {
  product: string;
  required: string;
  preferred: string;
  excluded: string;
  budget: string;
}

export interface Product {
  id: string;
  name: string;
  price: number;
  rating: number;
  reviews: number;
  image: string;
  matched: string[];
  unknown: string[];
  mismatched: string[];
}

export interface State {
  screen: Screen;
  input: string;
  useImages: boolean;
  attempts: number;
  referenceExpiresAt: number | null;
  finalExpiresAt: number | null;
  researchStep: number;
  revision: number;
  error: string | null;
  conditions: Conditions;
  conditionsDirty: boolean;
}

export type Action =
  | { type: "INPUT"; value: string }
  | { type: "ORGANIZE" }
  | { type: "ORGANIZED"; revision?: number }
  | { type: "IMAGES"; value: boolean }
  | { type: "EDIT_CONDITIONS"; value: Conditions }
  | { type: "APPLY_CONDITIONS" }
  | { type: "START_REFERENCE"; now: number }
  | { type: "REFERENCE_READY"; now: number; revision?: number }
  | { type: "APPROVE_REFERENCE"; now: number }
  | { type: "COMPARISONS_READY"; revision?: number }
  | { type: "REGENERATE"; now: number }
  | { type: "WITHOUT_IMAGES"; now: number }
  | { type: "FINALIZE"; now: number }
  | { type: "SEARCH"; now: number }
  | { type: "TICK"; revision?: number }
  | { type: "SHOW_RESULTS" }
  | { type: "BACK" }
  | { type: "CANCEL" }
  | { type: "RESET" }
  | { type: "FAIL"; message: string; revision?: number };

const APPROVAL_DURATION_MS = 15 * 60_000;
const MAX_REFERENCE_ATTEMPTS = 2;
const RESEARCH_STAGE_COUNT = 5;

export const DEFAULT_CONDITIONS: Conditions = {
  product: "メカニカルキーボード",
  required: "ワイヤレス接続、コンパクトなサイズ",
  preferred: "白い本体、静かな打鍵音",
  excluded: "テンキー付き、大きな本体",
  budget: "5,000円〜15,000円",
};

export const initialState: State = {
  screen: "input",
  input: "",
  useImages: false,
  attempts: 0,
  referenceExpiresAt: null,
  finalExpiresAt: null,
  researchStep: 0,
  revision: 0,
  error: null,
  conditions: { ...DEFAULT_CONDITIONS },
  conditionsDirty: false,
};

export function isBusy(state: State): boolean {
  return [
    "organizing",
    "referenceGenerating",
    "comparisonGenerating",
    "research",
  ].includes(state.screen);
}

function clearApprovals(state: State): State {
  return {
    ...state,
    referenceExpiresAt: null,
    finalExpiresAt: null,
    researchStep: 0,
    revision: state.revision + 1,
    error: null,
  };
}

function startReference(state: State): State {
  if (state.attempts >= MAX_REFERENCE_ATTEMPTS) {
    return {
      ...state,
      error: "参考画像の作成は2回までです。画像なしで続けられます。",
    };
  }
  return {
    ...clearApprovals(state),
    screen: "referenceGenerating",
    attempts: state.attempts + 1,
  };
}

export function reducer(state: State, action: Action): State {
  // A cancelled timer may finish after a new attempt has begun on the same screen.
  if (
    "revision" in action &&
    action.revision !== undefined &&
    action.revision !== state.revision
  ) {
    return state;
  }
  if ("now" in action && !Number.isFinite(action.now)) {
    return state;
  }
  if (
    isBusy(state) &&
    ![
      "ORGANIZED",
      "REFERENCE_READY",
      "COMPARISONS_READY",
      "TICK",
      "FAIL",
      "CANCEL",
      "RESET",
    ].includes(action.type)
  ) {
    return state;
  }

  switch (action.type) {
    case "INPUT":
      if (state.screen !== "input" || state.input === action.value) {
        return state;
      }
      return { ...clearApprovals(state), input: action.value };
    case "ORGANIZE":
      if (state.screen !== "input") {
        return state;
      }
      if (!state.input.trim() || state.input.length > 2_000) {
        return {
          ...state,
          error: "探したい商品を1〜2,000文字で入力してください。",
        };
      }
      return { ...clearApprovals(state), screen: "organizing" };
    case "ORGANIZED":
      if (state.screen !== "organizing") {
        return state;
      }
      return {
        ...state,
        screen: "review",
        conditions: { ...DEFAULT_CONDITIONS },
        conditionsDirty: false,
      };
    case "IMAGES":
      if (
        !["input", "review"].includes(state.screen) ||
        state.useImages === action.value
      ) {
        return state;
      }
      return { ...clearApprovals(state), useImages: action.value };
    case "EDIT_CONDITIONS":
      if (state.screen !== "review") {
        return state;
      }
      if (
        (Object.keys(state.conditions) as (keyof Conditions)[]).every(
          (key) => state.conditions[key] === action.value[key],
        )
      ) {
        return state;
      }
      return {
        ...clearApprovals(state),
        conditions: { ...action.value },
        conditionsDirty: true,
      };
    case "APPLY_CONDITIONS":
      if (state.screen !== "review" || !state.conditionsDirty) {
        return state;
      }
      if (!state.conditions.product.trim()) {
        return { ...state, error: "探す商品の種類を入力してください。" };
      }
      return { ...clearApprovals(state), conditionsDirty: false };
    case "START_REFERENCE":
      if (
        state.screen !== "review" ||
        !state.useImages ||
        state.conditionsDirty
      ) {
        return state;
      }
      return startReference(state);
    case "REFERENCE_READY":
      if (state.screen !== "referenceGenerating") {
        return state;
      }
      return {
        ...state,
        screen: "referenceReview",
        referenceExpiresAt: action.now + APPROVAL_DURATION_MS,
      };
    case "APPROVE_REFERENCE":
      if (state.screen !== "referenceReview") {
        return state;
      }
      if (
        state.error ||
        state.referenceExpiresAt === null ||
        action.now >= state.referenceExpiresAt
      ) {
        return {
          ...state,
          error:
            state.error ??
            "参考画像の確認期限が切れました。作り直すか、画像なしで続けてください。",
        };
      }
      return {
        ...state,
        screen: "comparisonGenerating",
        revision: state.revision + 1,
      };
    case "COMPARISONS_READY":
      if (state.screen !== "comparisonGenerating") {
        return state;
      }
      return { ...state, screen: "comparisonReview" };
    case "REGENERATE":
      if (
        !["referenceReview", "comparisonReview"].includes(state.screen) ||
        !state.useImages
      ) {
        return state;
      }
      return startReference(state);
    case "WITHOUT_IMAGES":
      if (
        !["review", "referenceReview", "comparisonReview"].includes(
          state.screen,
        ) ||
        state.conditionsDirty
      ) {
        return state;
      }
      return {
        ...clearApprovals(state),
        screen: "final",
        useImages: false,
        finalExpiresAt: action.now + APPROVAL_DURATION_MS,
      };
    case "FINALIZE":
      if (state.conditionsDirty) {
        return state;
      }
      if (
        state.screen !== "final" &&
        !(state.screen === "review" && !state.useImages) &&
        !(state.screen === "comparisonReview" && !state.error)
      ) {
        return state;
      }
      return {
        ...state,
        screen: "final",
        finalExpiresAt: action.now + APPROVAL_DURATION_MS,
        error: null,
      };
    case "SEARCH":
      if (state.screen !== "final") {
        return state;
      }
      if (state.finalExpiresAt === null || action.now >= state.finalExpiresAt) {
        return {
          ...state,
          error: "最終確認の期限が切れました。内容を再確認してください。",
        };
      }
      return {
        ...state,
        screen: "research",
        researchStep: 0,
        revision: state.revision + 1,
        error: null,
      };
    case "TICK": {
      if (state.screen !== "research") {
        return state;
      }
      const researchStep = state.researchStep + 1;
      return {
        ...state,
        researchStep,
        screen: researchStep >= RESEARCH_STAGE_COUNT ? "complete" : "research",
      };
    }
    case "SHOW_RESULTS":
      return state.screen === "complete"
        ? { ...state, screen: "results" }
        : state;
    case "BACK":
      if (state.screen === "review") {
        return { ...clearApprovals(state), screen: "input" };
      }
      if (
        ["referenceReview", "comparisonReview", "final"].includes(state.screen)
      ) {
        return { ...clearApprovals(state), screen: "review" };
      }
      return state;
    case "CANCEL":
      if (state.screen !== "research") {
        return state;
      }
      return {
        ...state,
        screen: "final",
        researchStep: 0,
        revision: state.revision + 1,
        error: null,
      };
    case "RESET":
      return {
        ...initialState,
        conditions: { ...DEFAULT_CONDITIONS },
        revision: state.revision + 1,
      };
    case "FAIL": {
      const recoveries: Partial<Record<Screen, Screen>> = {
        organizing: "input",
        referenceGenerating: "referenceReview",
        comparisonGenerating: "comparisonReview",
        research: "final",
      };
      const screen = recoveries[state.screen];
      if (!screen) {
        return state;
      }
      return {
        ...state,
        screen,
        researchStep: 0,
        revision: state.revision + 1,
        error: action.message,
      };
    }
  }
}

const DEMO_PRODUCTS: [string, number, number, number, string, string[]?][] = [
  ["Cloud 75 ワイヤレスキーボード", 8_980, 4.6, 128, "keyboard-white"],
  ["Quiet Type 68 コンパクト", 11_800, 4.4, 86, "keyboard-white"],
  ["Snow Desk 84 メカニカル", 12_600, 4.5, 204, "keyboard-white"],
  ["Mono Keys 75 ワイヤレス", 9_480, 4.2, 57, "keyboard-dark"],
  ["Soft Press 68 静音モデル", 13_200, 4.7, 93, "keyboard-white"],
  ["Work Form 80 コンパクト", 7_980, 4.1, 64, "keyboard-dark"],
  ["Daily Type 75 メカニカル", 6_980, 4.3, 142, "keyboard-white"],
  ["Studio Keys 84 ワイヤレス", 14_800, 4.6, 71, "keyboard-white"],
  ["Calm Desk 68 静音モデル", 10_800, 4.4, 116, "keyboard-dark"],
  ["Plain Type 75 コンパクト", 8_280, 4.0, 48, "keyboard-white"],
  ["Entry Form 87 メカニカル", 5_480, 4.1, 82, "keyboard-dark"],
  [
    "Wide Keys 104 フルサイズ",
    9_980,
    4.2,
    135,
    "keyboard-full",
    ["テンキー付き", "大きな本体"],
  ],
];

// Fixed synthetic listings keep input handling independent from search or inference.
export const PRODUCTS: Product[] = DEMO_PRODUCTS.map(
  ([name, price, rating, reviews, image, mismatched = []], index) => ({
    id: `mock-keyboard-${String(index + 1).padStart(2, "0")}`,
    name,
    price,
    rating,
    reviews,
    image: `/images/${image}.svg`,
    matched: index < 10 ? ["ワイヤレス接続", "コンパクト"] : ["メカニカル方式"],
    unknown: index % 3 === 0 ? ["静音性は未確認"] : ["接続可能な機器は未確認"],
    mismatched,
  }),
);
