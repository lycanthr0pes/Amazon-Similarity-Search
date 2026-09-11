import * as stylex from "@stylexjs/stylex";
import { useEffect, useReducer, useRef, useState } from "react";
import {
  Actions,
  Button,
  DeleteButton,
  Dialog,
  Dots,
  Generating,
  ImageCard,
  Note,
  ResearchProgress,
  Stepper,
  Toggle,
} from "./components";
import { initialState, isBusy, PRODUCTS, reducer, type Screen } from "./model";
import {
  deleteHistory,
  readHistory,
  saveHistory,
  HISTORY_TTL_MS,
  type HistoryEntry,
} from "./history";
import {
  ConditionEditor,
  ConditionSummary,
  ImageGallery,
  layout,
  MOCK_IMAGES,
  Results,
} from "./screens";

type Modal =
  | { kind: "regenerate" }
  | { kind: "image"; index: number; multiple: boolean }
  | { kind: "delete"; entry: HistoryEntry }
  | { kind: "cancel" }
  | { kind: "discard" }
  | null;
const TITLES: Record<Screen, string> = {
  input: "探しているものを、言葉で。",
  organizing: "条件を整理しています",
  review: "条件を確認",
  referenceGenerating: "参考画像を準備",
  referenceReview: "まず1枚、見た目を確認",
  comparisonGenerating: "比較画像を準備",
  comparisonReview: "比較画像を確認",
  final: "検索内容を最終確認",
  research: "商品を調査",
  complete: "商品を調査",
  results: "条件に近い商品",
};
const DELAYS = { organize: 900, image: 2400, research: 1100 };
const MOCK_NOTICE =
  "オフラインモック · 入力内容の理解・実検索は行わず、固定の合成条件・画像・商品を表示します。";

function stepFor(screen: Screen) {
  if (["input", "organizing", "review"].includes(screen)) {
    return 0;
  }
  if (screen.startsWith("reference") || screen.startsWith("comparison")) {
    return 1;
  }
  if (screen === "final") {
    return 2;
  }
  return screen === "results" ? 4 : 3;
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [view, setView] = useState<"search" | "history" | HistoryEntry>(
    "search",
  );
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [modalError, setModalError] = useState("");
  const [modal, setModal] = useState<Modal>(null);
  const [count, setCount] = useState(10);
  const [now, setNow] = useState(Date.now);
  const heading = useRef<HTMLHeadingElement>(null);
  const runId = useRef("");
  const pendingSave = useRef<HistoryEntry | null>(null);
  const savedIds = useRef(new Set<string>());
  const failedScenarios = useRef(new Set<string>());
  const scenario = useRef(
    new URLSearchParams(window.location.search).get("scenario") ?? "default",
  ).current;
  const busy = isBusy(state);
  const title =
    view === "history"
      ? "検索履歴"
      : typeof view === "object"
        ? "保存した検索結果"
        : TITLES[state.screen];
  const referenceExpired =
    state.referenceExpiresAt !== null && now >= state.referenceExpiresAt;
  const finalExpired =
    state.finalExpiresAt !== null && now >= state.finalExpiresAt;
  const products = scenario === "empty" ? [] : PRODUCTS;

  function failOnce(name: string) {
    if (scenario !== name || failedScenarios.current.has(name)) {
      return false;
    }
    failedScenarios.current.add(name);
    return true;
  }

  function refreshHistory() {
    try {
      setHistory(readHistory(window.sessionStorage, Date.now()));
      setHistoryError("");
    } catch {
      setHistoryError(
        "検索履歴を読み込めませんでした。ブラウザの保存設定を確認し、再読込してください。",
      );
    }
  }

  function persist(entry: HistoryEntry) {
    try {
      if (failOnce("save-error")) {
        throw new Error("mock save failure");
      }
      setHistory(saveHistory(window.sessionStorage, entry, Date.now()));
      savedIds.current.add(entry.id);
      pendingSave.current = null;
      setSaveError("");
    } catch {
      setSaveError(
        "結果を履歴に保存できませんでした。結果はこの画面で確認できます。",
      );
    }
  }

  useEffect(() => {
    refreshHistory();
  }, []);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, [state.screen, view]);
  useEffect(() => {
    if (!busy) {
      return;
    }
    const revision = state.revision;
    const delay =
      state.screen === "organizing"
        ? DELAYS.organize
        : state.screen === "research"
          ? DELAYS.research
          : DELAYS.image;
    const timer = window.setTimeout(() => {
      const failure =
        state.screen === "organizing"
          ? "organize-error"
          : state.screen === "referenceGenerating"
            ? "reference-error"
            : state.screen === "comparisonGenerating"
              ? "comparison-error"
              : "research-error";
      if (failOnce(failure)) {
        dispatch({
          type: "FAIL",
          revision,
          message:
            "処理を完了できませんでした。表示中の操作からやり直してください。（モックの失敗表示）",
        });
        return;
      }
      if (state.screen === "organizing") {
        dispatch({ type: "ORGANIZED", revision });
      }
      if (state.screen === "referenceGenerating") {
        dispatch({ type: "REFERENCE_READY", now: Date.now(), revision });
      }
      if (state.screen === "comparisonGenerating") {
        dispatch({ type: "COMPARISONS_READY", revision });
      }
      if (state.screen === "research") {
        dispatch({ type: "TICK", revision });
      }
    }, delay);
    return () => window.clearTimeout(timer);
  }, [busy, state.screen, state.revision, state.researchStep]);
  useEffect(() => {
    if (
      state.screen !== "complete" ||
      savedIds.current.has(runId.current) ||
      pendingSave.current
    ) {
      return;
    }
    const entry = {
      id: runId.current,
      createdAt: Date.now(),
      input: state.input,
      conditions: state.conditions,
      useImages: state.useImages,
      products,
    };
    pendingSave.current = entry;
    persist(entry);
  }, [state.screen]);

  useEffect(() => {
    const warnUnsaved = (event: BeforeUnloadEvent) => {
      if (pendingSave.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warnUnsaved);
    return () => window.removeEventListener("beforeunload", warnUnsaved);
  }, []);
  useEffect(() => {
    const expiredView =
      typeof view === "object" && now - view.createdAt >= HISTORY_TTL_MS;
    if (
      !historyError &&
      (expiredView ||
        history.some((entry) => now - entry.createdAt >= HISTORY_TTL_MS))
    ) {
      refreshHistory();
      if (expiredView) {
        setView("history");
      }
    }
  }, [now, history, historyError, view]);

  function newSearch() {
    if (pendingSave.current) {
      setModal({ kind: "discard" });
      return;
    }
    resetSearch();
  }

  function resetSearch() {
    pendingSave.current = null;
    setSaveError("");
    setView("search");
    setCount(10);
    dispatch({ type: "RESET" });
  }

  function startSearch() {
    if (finalExpired || state.screen !== "final") {
      return;
    }
    runId.current = crypto.randomUUID();
    pendingSave.current = null;
    setSaveError("");
    dispatch({ type: "SEARCH", now: Date.now() });
  }

  function removeEntry(entry: HistoryEntry) {
    try {
      if (failOnce("delete-error")) {
        throw new Error("mock delete failure");
      }
      setHistory(deleteHistory(window.sessionStorage, entry.id, Date.now()));
      setModal(null);
      setModalError("");
      if (typeof view === "object" && view.id === entry.id) {
        setView("history");
      }
    } catch {
      setModalError("履歴を削除できませんでした。履歴は残っています。");
    }
  }

  const summary = (
    <ConditionSummary
      conditions={state.conditions}
      input={state.input}
      useImages={state.useImages}
      variant={state.screen === "final" ? "cards" : "plain"}
    />
  );
  const openImage = (index: number, multiple = false) =>
    setModal({ kind: "image", index, multiple });
  return (
    <>
      <header {...stylex.props(layout.header)}>
        <div {...stylex.props(layout.brand)}>
          <span aria-hidden="true" {...stylex.props(layout.monogram)}>
            AE
          </span>
          <div>
            <p {...stylex.props(layout.brandName)}>Amazon Explorer</p>
            <p {...stylex.props(layout.small)}>
              {view === "history"
                ? "検索履歴"
                : typeof view === "object"
                  ? "履歴の詳細"
                  : ["条件整理", "参考画像", "最終確認", "商品調査", "結果"][
                      stepFor(state.screen)
                    ]}
            </p>
          </div>
        </div>
        <div {...stylex.props(layout.headerActions)}>
          <Button variant="primary" onClick={newSearch}>
            新しく検索
          </Button>
          <Button
            onClick={() => {
              if (view === "search") {
                refreshHistory();
                setView("history");
              } else {
                setView("search");
              }
            }}
          >
            {view === "search" ? "検索履歴" : "検索へ戻る"}
          </Button>
        </div>
      </header>
      <main
        {...stylex.props(layout.page, view !== "search" && layout.historyPage)}
      >
        {view === "search" && <Stepper current={stepFor(state.screen)} />}
        <div {...stylex.props(layout.intro)}>
          <p {...stylex.props(layout.eyebrow)}>
            {view === "search"
              ? `STEP ${String(stepFor(state.screen) + 1).padStart(2, "0")} / 05`
              : "SAVED SEARCHES"}
          </p>
          <h1 ref={heading} tabIndex={-1}>
            {title}
          </h1>
        </div>
        <div {...stylex.props(layout.intro)}>
          <Note>{MOCK_NOTICE}</Note>
        </div>
        <div aria-live="polite" aria-atomic="true">
          {state.error && view === "search" && (
            <p role="alert" {...stylex.props(layout.error)}>
              {state.error}
            </p>
          )}
          {saveError && view === "search" && (
            <div {...stylex.props(layout.error)}>
              <p>{saveError}</p>
              <Button
                onClick={() => {
                  if (pendingSave.current) {
                    persist(pendingSave.current);
                  }
                }}
              >
                保存を再試行
              </Button>
            </div>
          )}
        </div>
        {view === "history" ? (
          <div {...stylex.props(layout.stack)}>
            <Note>
              このタブのブラウザ内に最大30件・30日間保存します。タブを閉じると消去されます。再読込で検索は再実行しません。
            </Note>
            {historyError && (
              <div role="alert">
                <p>{historyError}</p>
                <Button onClick={refreshHistory}>再読込</Button>
              </div>
            )}
            {history.length === 0 && !historyError ? (
              <section {...stylex.props(layout.panel)}>
                <h2>検索履歴はまだありません</h2>
                <p>完了したモックの結果をここから見直せます。</p>
              </section>
            ) : (
              <ul
                aria-label="検索履歴一覧"
                {...stylex.props(layout.resultGrid, layout.historyGrid)}
              >
                {history.map((entry) => (
                  <li
                    key={entry.id}
                    {...stylex.props(layout.product, layout.historyCard)}
                  >
                    <p {...stylex.props(layout.small)}>
                      {new Date(entry.createdAt).toLocaleString("ja-JP")}
                    </p>
                    <p {...stylex.props(layout.small)}>
                      保存期限：
                      {new Date(
                        entry.createdAt + HISTORY_TTL_MS,
                      ).toLocaleString("ja-JP")}
                    </p>
                    <h4 {...stylex.props(layout.inputText)}>
                      {entry.conditions.product}
                    </h4>
                    <p {...stylex.props(layout.wrap)}>{entry.input}</p>
                    <p>
                      {entry.products.length}件 · 参考画像
                      {entry.useImages ? "あり" : "なし"}
                    </p>
                    <div {...stylex.props(layout.historyActions)}>
                      <DeleteButton
                        size="compact"
                        onClick={() => {
                          setModalError("");
                          setModal({ kind: "delete", entry });
                        }}
                      />
                      <Button
                        variant="primary"
                        size="compact"
                        onClick={() => {
                          setView(entry);
                          setCount(10);
                        }}
                      >
                        開く
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : typeof view === "object" ? (
          <div {...stylex.props(layout.stack)}>
            <section {...stylex.props(layout.panel, layout.stack)}>
              <p>{new Date(view.createdAt).toLocaleString("ja-JP")}</p>
              <ConditionSummary
                input={view.input}
                conditions={view.conditions}
                useImages={view.useImages}
                variant="cards"
                columns={2}
              />
              <Note>保存済みの合成結果です。商品検索は実行しません。</Note>
              <Actions
                left={
                  <DeleteButton
                    onClick={() => {
                      setModalError("");
                      setModal({ kind: "delete", entry: view });
                    }}
                  />
                }
              >
                <Button
                  onClick={() => {
                    refreshHistory();
                    setView("history");
                  }}
                >
                  履歴へ戻る
                </Button>
              </Actions>
            </section>
            <Results
              products={view.products}
              count={count}
              onCount={setCount}
            />
          </div>
        ) : (
          <>
            {(state.screen === "input" || state.screen === "organizing") && (
              <section {...stylex.props(layout.panel)}>
                <div {...stylex.props(layout.heroColumns)}>
                  <div>
                    <label htmlFor="query" {...stylex.props(layout.field)}>
                      <h3>探している商品</h3>
                      <span>
                        商品・予算・ほしい特徴を自由に書いてください。
                      </span>
                    </label>
                    <textarea
                      id="query"
                      aria-describedby="query-count query-help"
                      readOnly={busy}
                      value={state.input}
                      onChange={(event) =>
                        dispatch({ type: "INPUT", value: event.target.value })
                      }
                      placeholder="例：1万5千円以内で、白くて静かなワイヤレスキーボード。テンキー付きは避けたい。"
                      {...stylex.props(layout.input, layout.textarea)}
                    />
                    <div id="query-count" {...stylex.props(layout.counter)}>
                      <span>
                        {state.input.length > 2000 &&
                          "2,000文字以内で入力してください"}
                      </span>
                      <span>
                        {state.input.length.toLocaleString("ja-JP")} / 2,000
                      </span>
                    </div>
                  </div>
                  <aside {...stylex.props(layout.stack)}>
                    <p id="query-help" {...stylex.props(layout.small)}>
                      モックでは、どんな文章にも同じキーボードのデモ条件を表示します。
                    </p>
                  </aside>
                </div>
                <Toggle
                  label="参考画像を使う"
                  checked={state.useImages}
                  disabled={busy}
                  onChange={(value) => dispatch({ type: "IMAGES", value })}
                />
                <Actions>
                  <Button
                    variant="primary"
                    disabled={
                      busy || !state.input.trim() || state.input.length > 2000
                    }
                    onClick={() => dispatch({ type: "ORGANIZE" })}
                  >
                    {busy ? (
                      <Dots label="整理中" />
                    ) : state.error ? (
                      "再試行"
                    ) : (
                      "条件を整理"
                    )}
                  </Button>
                </Actions>
              </section>
            )}
            {state.screen === "review" && (
              <section {...stylex.props(layout.panel)}>
                <div {...stylex.props(layout.stack)}>
                  <div>
                    <h3>入力した文章</h3>
                    <p {...stylex.props(layout.wrap, layout.inputText)}>
                      {state.input}
                    </p>
                  </div>
                  <Note>
                    以下は入力から推論した内容ではなく、固定のデモ条件です。編集内容は確認画面へ反映し、商品・価格・順位は固定のまま表示します。
                  </Note>
                  <ConditionEditor
                    conditions={state.conditions}
                    onChange={(value) =>
                      dispatch({ type: "EDIT_CONDITIONS", value })
                    }
                  />
                  {state.conditionsDirty && (
                    <div role="status">
                      <p>
                        内容が変更されました。次へ進む前に更新してください。
                      </p>
                      <Button
                        onClick={() => dispatch({ type: "APPLY_CONDITIONS" })}
                      >
                        変更を反映
                      </Button>
                    </div>
                  )}
                  <Toggle
                    label={`参考画像を使う（残り${2 - state.attempts}回）`}
                    checked={state.useImages}
                    onChange={(value) => dispatch({ type: "IMAGES", value })}
                  />
                </div>
                <Actions
                  left={
                    <Button onClick={() => dispatch({ type: "BACK" })}>
                      入力へ戻る
                    </Button>
                  }
                >
                  <Button
                    variant="primary"
                    disabled={
                      state.conditionsDirty ||
                      (state.useImages && state.attempts >= 2)
                    }
                    onClick={() =>
                      dispatch(
                        state.useImages
                          ? { type: "START_REFERENCE", now: Date.now() }
                          : { type: "WITHOUT_IMAGES", now: Date.now() },
                      )
                    }
                  >
                    {state.useImages ? "参考画像を生成" : "画像なしで進む"}
                  </Button>
                </Actions>
              </section>
            )}
            {(state.screen === "referenceGenerating" ||
              state.screen === "comparisonGenerating") && (
              <section {...stylex.props(layout.panel)}>
                <div {...stylex.props(layout.stack)}>
                  <h3>
                    {state.screen === "referenceGenerating"
                      ? "参考画像を1枚生成しています"
                      : "比較用の偽画像を準備しています"}
                  </h3>
                  <div {...stylex.props(layout.imageRow)}>
                    {state.screen === "referenceGenerating" ? (
                      <Generating label="参考画像" />
                    ) : (
                      <>
                        <ImageCard
                          {...MOCK_IMAGES[0]}
                          onOpen={() => openImage(0)}
                        />
                        <Generating label="比較用の偽画像：色" />
                        <Generating label="比較用の偽画像：形" />
                      </>
                    )}
                  </div>
                  <Note>
                    生成中の表示を模擬しています。実際の画像生成は行いません。
                  </Note>
                  <Actions>
                    <Button disabled>生成中</Button>
                  </Actions>
                </div>
              </section>
            )}
            {state.screen === "referenceReview" && (
              <section {...stylex.props(layout.panel)}>
                <div {...stylex.props(layout.stack)}>
                  {!state.error && (
                    <div {...stylex.props(layout.imageRow)}>
                      <ImageCard
                        {...MOCK_IMAGES[0]}
                        onOpen={() => openImage(0)}
                      />
                      <div {...stylex.props(layout.stack)}>
                        <h3>このイメージでよいですか？</h3>
                        <p>了承後に、比較用の偽画像を生成します。</p>
                        <Note>
                          色と形をそれぞれ変更した2枚を用意します。参考画像は実商品の仕様を証明するものではありません。
                        </Note>
                      </div>
                    </div>
                  )}
                  <p>作り直せる回数：残り{2 - state.attempts}回</p>
                  {referenceExpired && (
                    <p role="alert">
                      確認の期限が切れました。作り直すか、画像なしで進んでください。
                    </p>
                  )}
                </div>
                <Actions
                  left={
                    <div {...stylex.props(layout.imageRow)}>
                      <Button onClick={() => dispatch({ type: "BACK" })}>
                        条件へ戻る
                      </Button>
                      <Button
                        disabled={state.attempts >= 2}
                        onClick={() => setModal({ kind: "regenerate" })}
                      >
                        作り直す
                      </Button>
                    </div>
                  }
                >
                  <Button
                    onClick={() =>
                      dispatch({ type: "WITHOUT_IMAGES", now: Date.now() })
                    }
                  >
                    画像なしで進む
                  </Button>
                  <Button
                    variant="primary"
                    disabled={referenceExpired || !!state.error}
                    onClick={() =>
                      dispatch({ type: "APPROVE_REFERENCE", now: Date.now() })
                    }
                  >
                    了承して生成
                  </Button>
                </Actions>
              </section>
            )}
            {state.screen === "comparisonReview" && (
              <section {...stylex.props(layout.panel)}>
                {!state.error && (
                  <ImageGallery onOpen={(index) => openImage(index, true)} />
                )}
                <p>作り直せる回数：残り{2 - state.attempts}回</p>
                <Actions
                  left={
                    <div {...stylex.props(layout.imageRow)}>
                      <Button onClick={() => dispatch({ type: "BACK" })}>
                        条件へ戻る
                      </Button>
                      <Button
                        disabled={state.attempts >= 2}
                        onClick={() => setModal({ kind: "regenerate" })}
                      >
                        作り直す
                      </Button>
                    </div>
                  }
                >
                  <Button
                    onClick={() =>
                      dispatch({ type: "WITHOUT_IMAGES", now: Date.now() })
                    }
                  >
                    画像なしで進む
                  </Button>
                  <Button
                    variant="primary"
                    disabled={!!state.error}
                    onClick={() =>
                      dispatch({ type: "FINALIZE", now: Date.now() })
                    }
                  >
                    最終確認へ
                  </Button>
                </Actions>
              </section>
            )}
            {state.screen === "final" && (
              <section {...stylex.props(layout.panel)}>
                <div {...stylex.props(layout.heroColumns)}>
                  {summary}
                  <aside {...stylex.props(layout.stack)}>
                    <h3>今回の検索</h3>
                    <p>
                      対象：ローカルの合成商品
                      <br />
                      比較件数：{products.length}件<br />
                      初期表示：最大10件
                    </p>
                    <Note>
                      この承認で商品調査のモックを1回実行します。外部への送信・実検索・費用の発生はありません。
                    </Note>
                  </aside>
                </div>
                {state.useImages && (
                  <div {...stylex.props(layout.stack)}>
                    <h3>採用する画像</h3>
                    <div {...stylex.props(layout.imageRow)}>
                      {MOCK_IMAGES.map((item, index) => (
                        <ImageCard
                          key={item.src}
                          {...item}
                          onOpen={() => openImage(index, true)}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {finalExpired && (
                  <div role="alert">
                    <p>確認の期限が切れました。内容を再確認してください。</p>
                    <Button
                      onClick={() =>
                        dispatch({ type: "FINALIZE", now: Date.now() })
                      }
                    >
                      内容を再確認
                    </Button>
                  </div>
                )}
                <Actions
                  left={
                    <Button onClick={() => dispatch({ type: "BACK" })}>
                      条件へ戻る
                    </Button>
                  }
                >
                  <Button
                    variant="primary"
                    disabled={finalExpired}
                    onClick={startSearch}
                  >
                    {state.error ? "再試行" : "検索"}
                  </Button>
                </Actions>
              </section>
            )}
            {(state.screen === "research" || state.screen === "complete") && (
              <>
                <div {...stylex.props(layout.twoColumns)}>
                  <div {...stylex.props(layout.stack)}>
                    <p role="status">
                      {state.screen === "complete"
                        ? "すべての工程が完了しました。結果を確認できます。"
                        : "合成商品の調査と比較を模擬しています。"}
                    </p>
                    <ResearchProgress current={state.researchStep} />
                  </div>
                  <aside {...stylex.props(layout.panel)}>{summary}</aside>
                </div>
                <Actions
                  left={
                    state.screen === "research" && (
                      <Button
                        variant="danger"
                        onClick={() => setModal({ kind: "cancel" })}
                      >
                        検索を中止
                      </Button>
                    )
                  }
                >
                  <Button
                    variant="primary"
                    disabled={state.screen !== "complete"}
                    onClick={() => dispatch({ type: "SHOW_RESULTS" })}
                  >
                    結果を見る
                  </Button>
                </Actions>
              </>
            )}
            {state.screen === "results" && (
              <Results products={products} count={count} onCount={setCount} />
            )}
          </>
        )}
        <footer {...stylex.props(layout.footer)}>
          <span>Amazon Explorer</span>
          <span>オフラインモック · 画面と操作の確認用</span>
        </footer>
      </main>
      {modal?.kind === "regenerate" && (
        <Dialog title="参考画像を作り直す" onClose={() => setModal(null)}>
          <div {...stylex.props(layout.stack)}>
            <p>参考画像1枚を作り直します。作成済みの偽画像も取り消されます。</p>
            <Note>
              現在：残り{2 - state.attempts}回 · 実行後：残り
              {1 - state.attempts}回
            </Note>
          </div>
          <Actions>
            <Button data-safe-focus onClick={() => setModal(null)}>
              キャンセル
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                setModal(null);
                dispatch({ type: "REGENERATE", now: Date.now() });
              }}
            >
              作り直す
            </Button>
          </Actions>
        </Dialog>
      )}
      {modal?.kind === "image" && (
        <Dialog
          title={MOCK_IMAGES[modal.index].label}
          onClose={() => setModal(null)}
        >
          <img
            src={MOCK_IMAGES[modal.index].src}
            alt={MOCK_IMAGES[modal.index].label}
            {...stylex.props(layout.lightbox)}
          />
          <Note>AI生成イメージのモック · 固定の合成画像</Note>
          <Actions
            left={
              modal.multiple && (
                <>
                  <Button
                    disabled={modal.index === 0}
                    onClick={() =>
                      setModal({ ...modal, index: modal.index - 1 })
                    }
                  >
                    前へ
                  </Button>
                  <Button
                    disabled={modal.index === MOCK_IMAGES.length - 1}
                    onClick={() =>
                      setModal({ ...modal, index: modal.index + 1 })
                    }
                  >
                    次へ
                  </Button>
                </>
              )
            }
          >
            <Button data-safe-focus onClick={() => setModal(null)}>
              閉じる
            </Button>
          </Actions>
        </Dialog>
      )}
      {modal?.kind === "cancel" && (
        <Dialog title="商品調査を中止" onClose={() => setModal(null)}>
          <p>商品調査のモックを中止し、最終確認に戻ります。</p>
          <Actions
            left={
              <Button
                variant="danger"
                onClick={() => {
                  setModal(null);
                  dispatch({ type: "CANCEL" });
                }}
              >
                中止
              </Button>
            }
          >
            <Button data-safe-focus onClick={() => setModal(null)}>
              キャンセル
            </Button>
          </Actions>
        </Dialog>
      )}
      {modal?.kind === "discard" && (
        <Dialog title="未保存の結果を破棄" onClose={() => setModal(null)}>
          <p>
            履歴に保存できていない結果があります。新しい検索を始めると、この結果を失います。
          </p>
          <Actions
            left={
              <Button
                variant="danger"
                onClick={() => {
                  setModal(null);
                  resetSearch();
                }}
              >
                結果を破棄
              </Button>
            }
          >
            <Button data-safe-focus onClick={() => setModal(null)}>
              キャンセル
            </Button>
          </Actions>
        </Dialog>
      )}
      {modal?.kind === "delete" && (
        <Dialog
          title="履歴を削除"
          onClose={() => {
            setModal(null);
            setModalError("");
          }}
        >
          <p>
            「{modal.entry.conditions.product}
            」の履歴を削除します。この操作は元に戻せません。
          </p>
          {modalError && <p role="alert">{modalError}</p>}
          <Actions
            left={
              <DeleteButton
                onClick={() => {
                  removeEntry(modal.entry);
                }}
              />
            }
          >
            <Button
              data-safe-focus
              onClick={() => {
                setModal(null);
                setModalError("");
              }}
            >
              キャンセル
            </Button>
          </Actions>
        </Dialog>
      )}
    </>
  );
}
