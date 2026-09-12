import {
  ImagePromptEditor,
  validPrompts,
  type ImagePrompts,
} from "./image-prompts";
import * as stylex from "@stylexjs/stylex";
import { useEffect, useRef, useState } from "react";
import {
  Actions,
  Button,
  Dialog,
  Dots,
  Generating,
  ImageCard,
  Note,
  ResearchProgress,
  Stepper,
  Toggle,
} from "./components";
import { layout } from "./screens";
import { SearchHeader } from "./search-chrome";
import { ConnectedProducts } from "./ConnectedProducts";
import { SavedConditions, ConditionGroupEditor } from "./ConnectedConditions";
import {
  conditionValues,
  conditionsChanged,
  conditionEditError,
  editedConditionSource,
  type ConditionDraft,
} from "./condition-editor";
import { ConnectedHistory } from "./ConnectedHistory";
import { type SearchStage, type SearchView } from "./connected-api";

import { useSearchClient } from "./search-client";

const TITLES: Record<SearchStage, string> = {
  idle: "探しているものを、言葉で。",
  working: "処理しています",
  query: "条件を確認",
  clarification: "文章を修正してください",
  reference: "まず1枚、見た目を確認",
  comparison: "比較画像を確認",
  final: "検索内容を最終確認",
  attributes: "商品の条件を確認",
  complete: "商品を調査",
  failed: "処理を停止しました",
  expired: "確認の期限が切れました",
  cancelled: "検索を中止しました",
};
const STAGES = ["条件整理", "参考画像", "最終確認", "商品調査", "結果"];

export default function ConnectedApp() {
  const { readSearch, sendSearch, offline } = useSearchClient();
  const [historyOpen, setHistoryOpen] = useState(
    location.hash.startsWith("#history"),
  );
  const [view, setView] = useState<SearchView | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const query = 0;
  const [productDraft, setProductDraft] = useState("");
  const [conditionDraft, setConditionDraft] = useState<ConditionDraft>({
    required: "",
    preferred: "",
    excluded: "",
    neutral: "",
  });
  const reviewKey = JSON.stringify(view?.conditionReview);
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [image, setImage] = useState<number | null>(null);
  const [showResults, setShowResults] = useState(false);
  const [draft, setDraft] = useState("");
  const [useImages, setUseImages] = useState(false);
  const [editing, setEditing] = useState(false);
  const [modal, setModal] = useState<
    "regenerate" | "regenerate_comparisons" | "discard" | "cancel" | null
  >(null);
  const promptKey = JSON.stringify(view?.imagePrompts ?? null);
  const [prompts, setPrompts] = useState<ImagePrompts | null>(null);
  useEffect(() => {
    setPrompts(JSON.parse(promptKey) as ImagePrompts | null);
  }, [promptKey]);
  const referenceDirty =
    !!prompts && prompts.reference !== view?.imagePrompts?.reference;
  const comparisonDirty =
    !!prompts &&
    JSON.stringify(prompts.comparison) !==
      JSON.stringify(view?.imagePrompts?.comparison);
  const invalidPrompts = !!prompts && !validPrompts(prompts);
  const sending = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const current = await readSearch();
        if (active) {
          setView((previous) =>
            previous && previous.revision > current.revision
              ? previous
              : current,
          );
          setError("");
        }
      } catch {
        if (active) {
          setError(
            "接続状態を確認できません。処理を再送せず、状態の再取得を待っています。",
          );
        }
      } finally {
        if (active) {
          timer = setTimeout(refresh, 1000);
        }
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [readSearch]);
  useEffect(() => {
    const update = () => setHistoryOpen(location.hash.startsWith("#history"));
    addEventListener("hashchange", update);
    return () => removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    if (view?.historyOnly) {
      setHistoryOpen(true);
    }
  }, [view?.historyOnly]);
  function toggleHistory() {
    const open = !historyOpen;
    history.replaceState(
      null,
      "",
      location.pathname + location.search + (open ? "#history" : ""),
    );
    setHistoryOpen(open);
  }
  useEffect(() => {
    if (!historyOpen) {
      heading.current?.focus({ preventScroll: true });
    }
  }, [view?.stage, showResults, historyOpen, editing]);
  useEffect(() => {
    setDraft(view?.input ?? "");
  }, [view?.input]);
  useEffect(() => {
    setProductDraft(view?.productName ?? "");
    setConditionDraft(conditionValues(view ?? { stage: "idle", revision: 0 }));
  }, [view?.productName, view?.conditionText, view?.input, reviewKey]);
  useEffect(() => {
    if (view?.stage === "idle") {
      setShowResults(false);
      setEditing(false);
      setSelections({});
      setUseImages(false);
    }
  }, [view?.stage]);
  useEffect(() => {
    if (view?.canGenerateImages === false) setUseImages(false);
  }, [view?.canGenerateImages]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (view?.canRetrySave) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    addEventListener("beforeunload", warn);
    return () => removeEventListener("beforeunload", warn);
  }, [view?.canRetrySave]);
  async function execute(action: string, values = {}) {
    if (!view || sending.current || error) {
      return;
    }
    sending.current = true;
    setPending(true);
    try {
      const next = await sendSearch(action, view, {
        ...values,
        ...(["start", "revise"].includes(action)
          ? { imageMode: useImages ? "on" : "off" }
          : {}),
      });
      setView(next);
      if (["revise", "reset"].includes(action)) {
        setEditing(false);
        setShowResults(false);
        setImage(null);
      }
      if (action === "reset") {
        history.replaceState(null, "", location.pathname + location.search);
        setHistoryOpen(false);
      }
    } catch {
      setError(
        "受付状態を確認しています。画面を再読込しても同じ処理を繰り返しません。",
      );
    } finally {
      sending.current = false;
      setPending(false);
    }
  }
  function newSearch() {
    if (view?.canRetrySave) {
      setModal("discard");
    } else {
      void execute("reset");
    }
  }
  const action = view?.workingAction;
  const confirming =
    view?.stage === "working" &&
    ["final", "without_images"].includes(action ?? "");
  const stage = confirming ? "final" : (view?.stage ?? "idle");
  const organizing =
    stage === "working" && ["start", "revise", "reset"].includes(action ?? "");
  const generating =
    stage === "working" &&
    [
      "reference",
      "regenerate",
      "comparison",
      "regenerate_comparisons",
    ].includes(action ?? "");
  const researching =
    (stage === "working" &&
      ["search", "rank", "retry_save"].includes(action ?? "")) ||
    stage === "attributes" ||
    stage === "complete";
  const busy = pending || view?.stage === "working" || !view || Boolean(error);
  const validInput =
    draft.trim().length > 0 && Array.from(draft).length <= 2000;
  const imagePreparationChanged = useImages && view?.imageMode === "off";
  const termsChanged =
    Boolean(view?.editable) &&
    (imagePreparationChanged ||
      productDraft !== (view?.productName ?? "") ||
      (view && conditionsChanged(view, conditionDraft)));
  const revisedSource = view
    ? editedConditionSource(view, productDraft, conditionDraft)
    : "";
  const conditionError = view ? conditionEditError(view, conditionDraft) : null;
  const validTerms =
    productDraft.trim().length > 0 &&
    Array.from(productDraft.trim()).length <= 100 &&
    !/[。\n\r]/.test(productDraft) &&
    Array.from(revisedSource).length <= 2000 &&
    !conditionError;
  const changed =
    Boolean(view?.editable) && (draft !== view?.input || termsChanged);
  const step =
    editing || organizing || ["idle", "query", "clarification"].includes(stage)
      ? 0
      : generating || ["reference", "comparison"].includes(stage)
        ? 1
        : stage === "final"
          ? 2
          : showResults
            ? 4
            : 3;
  const images = view?.images ?? [];
  const title = editing
    ? "入力内容を修正"
    : showResults
      ? "条件に近い商品"
      : organizing
        ? "条件を整理しています"
        : generating
          ? ["comparison", "regenerate_comparisons"].includes(action ?? "")
            ? "比較画像を準備"
            : "参考画像を準備"
          : researching
            ? "商品を調査"
            : TITLES[stage];
  const inputVisible =
    stage === "idle" || organizing || editing || stage === "clarification";
  const back = (
    <Button
      disabled={busy || !view?.canRevise}
      onClick={() => setEditing(true)}
    >
      条件へ戻る
    </Button>
  );
  const skip = (
    <Button
      disabled={busy || changed || !view?.canSkipImages}
      onClick={() => void execute("without_images", { index: query })}
    >
      画像なしで進む
    </Button>
  );
  function gallery() {
    return (
      <div {...stylex.props(layout.imageGallery)}>
        {images.map((src, index) => (
          <ImageCard
            key={`${index}-${src}`}
            src={src}
            label={
              index === 0
                ? "参考画像"
                : `比較画像：${view?.conditions?.[index - 1] ?? "外観条件"}を変更`
            }
            onOpen={() => setImage(index)}
            imageKind={view?.mode === "live" ? "generated" : "mock"}
          />
        ))}
      </div>
    );
  }
  return (
    <>
      <SearchHeader
        section={historyOpen ? "検索履歴" : STAGES[step]}
        historyOpen={historyOpen}
        onNew={view?.historyOnly ? undefined : newSearch}
        disabled={busy || !view?.canReset}
        onHistory={
          view?.historyAvailable && !view.historyOnly
            ? toggleHistory
            : undefined
        }
      />
      {historyOpen && <ConnectedHistory />}
      <div hidden={historyOpen || view?.historyOnly}>
        <main {...stylex.props(layout.page)}>
          <Stepper current={step} />
          <div {...stylex.props(layout.intro)}>
            <p {...stylex.props(layout.eyebrow)}>
              STEP {String(step + 1).padStart(2, "0")} / 05
            </p>
            <h1 ref={heading} tabIndex={-1}>
              {title}
            </h1>
          </div>
          <div {...stylex.props(layout.intro)}>
            <Note>
              {!view
                ? "接続状態を確認しています。"
                : offline
                  ? "オフラインモック · 入力内容の理解・実検索は行わず、固定の合成条件・画像・商品を表示します。"
                  : view.mode === "fixture"
                    ? "オフライン接続テスト · 固定の合成応答を使っています。"
                    : "確認した条件でAmazon.co.jpの商品を比較します。"}
            </Note>
          </div>
          {error && (
            <p role="alert" {...stylex.props(layout.error)}>
              {error}
            </p>
          )}
          {view?.canRetrySave && (
            <div role="alert" {...stylex.props(layout.error)}>
              <p>{view.message}</p>
              <Button
                disabled={busy}
                onClick={() => void execute("retry_save")}
              >
                保存を再試行
              </Button>
            </div>
          )}
          {inputVisible && (
            <section {...stylex.props(layout.panel)}>
              <div {...stylex.props(layout.heroColumns)}>
                <div>
                  <label
                    htmlFor="connected-query"
                    {...stylex.props(layout.field)}
                  >
                    <h3>探している商品</h3>
                    <span>商品・予算・ほしい特徴を自由に書いてください。</span>
                  </label>
                  <textarea
                    id="connected-query"
                    aria-label="探している商品・条件"
                    aria-describedby="connected-count"
                    value={draft}
                    readOnly={busy}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder="例：1万5千円以内で、白くて静かなワイヤレスキーボード。テンキー付きは避けたい。"
                    {...stylex.props(layout.input, layout.textarea)}
                  />
                  <div id="connected-count" {...stylex.props(layout.counter)}>
                    <span>
                      {Array.from(draft).length > 2000 &&
                        "2,000文字以内で入力してください"}
                    </span>
                    <span>
                      {Array.from(draft).length.toLocaleString("ja-JP")} / 2,000
                    </span>
                  </div>
                </div>
              </div>
              {stage === "clarification" && (
                <div role="alert">
                  <p>{view?.message}</p>
                  {view?.conditionIssues?.map((issue) => (
                    <p key={issue.start}>修正箇所：{issue.quote}</p>
                  ))}
                </div>
              )}
              <Toggle
                label="参考画像を使う"
                checked={useImages}
                disabled={busy}
                onChange={setUseImages}
              />
              <Actions
                left={
                  editing && (
                    <Button
                      disabled={busy}
                      onClick={() => {
                        setEditing(false);
                        setDraft(view?.input ?? "");
                      }}
                    >
                      修正をやめる
                    </Button>
                  )
                }
              >
                <Button
                  variant="primary"
                  disabled={
                    busy ||
                    !validInput ||
                    (stage !== "idle" && !view?.canRevise && !organizing)
                  }
                  onClick={() =>
                    void execute(stage === "idle" ? "start" : "revise", {
                      source: draft,
                    })
                  }
                >
                  {organizing ? (
                    <Dots label="整理中" />
                  ) : stage === "idle" ? (
                    "条件を整理"
                  ) : (
                    "変更を反映"
                  )}
                </Button>
              </Actions>
            </section>
          )}
          {!inputVisible && !showResults && stage === "query" && (
            <section {...stylex.props(layout.panel)}>
              <div {...stylex.props(layout.stack)}>
                <div>
                  <h3>入力した文章</h3>
                  <p {...stylex.props(layout.wrap, layout.inputText)}>
                    {view?.input}
                  </p>
                </div>
                {view?.productName !== undefined ? (
                  <>
                    <label {...stylex.props(layout.field)}>
                      商品名
                      <input
                        aria-label="商品名"
                        value={productDraft}
                        readOnly={busy || !view?.canRevise}
                        onChange={(e) => setProductDraft(e.target.value)}
                        {...stylex.props(layout.input)}
                      />
                    </label>
                    <ConditionGroupEditor
                      value={conditionDraft}
                      onChange={setConditionDraft}
                      readOnly={busy || !view?.canRevise}
                    />
                    {termsChanged && (
                      <div role="status">
                        <p>
                          {imagePreparationChanged
                            ? "変更を反映すると、画像比較に使う見た目の条件を整理します。"
                            : "変更を反映すると、商品名と条件の同義語・英訳を再取得します。"}
                        </p>
                        {!validTerms && (
                          <p>
                            {conditionError ??
                              "商品名は文区切りを含めず100文字以内、全体は2,000文字以内で入力してください。"}
                          </p>
                        )}
                        <Button
                          disabled={busy || !validTerms || !view?.canRevise}
                          onClick={() =>
                            void execute("revise", { source: revisedSource })
                          }
                        >
                          変更を反映
                        </Button>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <SavedConditions
                      view={{
                        ...view!,
                        imageMode: useImages ? undefined : "off",
                      }}
                      cards
                      includeInput={false}
                    />
                    <label {...stylex.props(layout.field)}>
                      文章を修正
                      <textarea
                        aria-label="探している商品・条件"
                        value={draft}
                        readOnly={busy || !view?.canRevise}
                        onChange={(e) => setDraft(e.target.value)}
                        {...stylex.props(layout.input, layout.textarea)}
                      />
                    </label>
                    {changed && (
                      <div role="status">
                        <p>
                          内容が変更されました。次へ進む前に更新してください。
                        </p>
                        <Button
                          disabled={busy || !validInput || !view?.canRevise}
                          onClick={() =>
                            void execute("revise", { source: draft })
                          }
                        >
                          変更を反映
                        </Button>
                      </div>
                    )}
                  </>
                )}
                <Toggle
                  label={`参考画像を使う${view?.referenceRemaining !== undefined ? `（残り${view.referenceRemaining}回）` : ""}`}
                  checked={useImages}
                  disabled={
                    busy ||
                    (view?.canGenerateImages === false &&
                      view?.imageMode !== "off") ||
                    (view?.imageMode === "off" && !view.canRevise)
                  }
                  onChange={setUseImages}
                />
                {view?.canGenerateImages === false &&
                  view?.imageMode !== "off" && (
                    <Note>
                      見た目の条件がないため、画像なしで検索できます。
                    </Note>
                  )}
                {useImages && prompts && (
                  <ImagePromptEditor
                    value={prompts}
                    onChange={setPrompts}
                    disabled={busy}
                    referenceOnly
                  />
                )}
                {view?.editable && !view.canRevise && (
                  <Note>
                    この検索での再整理は上限に達しました。新しく検索することもできます。
                  </Note>
                )}
              </div>
              <Actions
                left={
                  <Button
                    disabled={busy || !view?.canRevise}
                    onClick={() => {
                      if (termsChanged) setDraft(revisedSource);
                      setEditing(true);
                    }}
                  >
                    入力へ戻る
                  </Button>
                }
              >
                <Button
                  variant="primary"
                  disabled={
                    busy ||
                    changed ||
                    (useImages &&
                      (view?.canGenerateImages === false || invalidPrompts))
                  }
                  onClick={() =>
                    void execute(useImages ? "reference" : "without_images", {
                      index: query,
                      ...(useImages && prompts
                        ? { prompt: prompts.reference }
                        : {}),
                    })
                  }
                >
                  {useImages ? "参考画像を生成" : "画像なしで進む"}
                </Button>
              </Actions>
            </section>
          )}
          {generating && (
            <section {...stylex.props(layout.panel, layout.stack)}>
              <h3>
                {["comparison", "regenerate_comparisons"].includes(action ?? "")
                  ? "比較用の画像を準備しています"
                  : "参考画像を1枚生成しています"}
              </h3>
              <div {...stylex.props(layout.imageRow)}>
                {["comparison", "regenerate_comparisons"].includes(
                  action ?? "",
                ) &&
                  images[0] && (
                    <ImageCard
                      src={images[0]}
                      label="参考画像"
                      onOpen={() => setImage(0)}
                      imageKind="generated"
                    />
                  )}
                {["comparison", "regenerate_comparisons"].includes(
                  action ?? "",
                ) ? (
                  (view?.conditions ?? ["外観条件"]).map((c) => (
                    <Generating key={c} label={`比較画像：${c}`} />
                  ))
                ) : (
                  <Generating label="参考画像" />
                )}
              </div>
              <Actions>
                <Button disabled>生成中</Button>
              </Actions>
            </section>
          )}
          {!editing &&
            !showResults &&
            [
              "reference",
              "comparison",
              "final",
              "expired",
              "failed",
              "cancelled",
            ].includes(stage) && (
              <section {...stylex.props(layout.panel, layout.stack)}>
                {stage === "final" ? (
                  <div {...stylex.props(layout.heroColumns)}>
                    <SavedConditions view={view!} cards />
                    <aside {...stylex.props(layout.stack)}>
                      <h3>今回の検索</h3>
                      <p>
                        対象：Amazon.co.jp
                        <br />
                        比較件数：最大24件
                        <br />
                        初期表示：最大10件
                      </p>
                      <div {...stylex.props(layout.field)}>
                        <span>商品名</span>
                        <div
                          {...stylex.props(layout.inputText)}
                          data-testid="final-product-name"
                        >
                          {view?.productName ?? view?.selectedQuery}
                        </div>
                      </div>
                    </aside>
                  </div>
                ) : null}
                {images.length > 0 &&
                  (stage === "reference" ? (
                    <div {...stylex.props(layout.imageRow)}>
                      {gallery()}
                      <div>
                        <h3>このイメージでよいですか？</h3>
                        <p>了承後に、条件別の比較画像を生成します。</p>
                        <Note>
                          参考画像は実商品の仕様を証明するものではありません。
                        </Note>
                      </div>
                    </div>
                  ) : (
                    gallery()
                  ))}
                {prompts &&
                  view?.imageMode !== "off" &&
                  ["reference", "comparison", "failed"].includes(stage) && (
                    <ImagePromptEditor
                      value={prompts}
                      onChange={setPrompts}
                      disabled={busy}
                      referenceDisabled={!view?.canRegenerate}
                      labels={view?.conditionLabels}
                    />
                  )}
                {(referenceDirty ||
                  (comparisonDirty && stage !== "reference")) &&
                  !busy && (
                    <p role="status">
                      変更したプロンプトで画像を作り直してください。
                    </p>
                  )}
                {view?.referenceRemaining !== undefined &&
                  view.imageMode !== "off" && (
                    <p>作り直せる回数：残り{view.referenceRemaining}回</p>
                  )}
                {view?.expiresAt && (
                  <p {...stylex.props(layout.small)}>
                    画像確認期限：
                    {new Date(view.expiresAt).toLocaleString("ja-JP")}
                  </p>
                )}
                {view?.imageMode === "off" && (
                  <Note>
                    画像比較なし：参考・比較画像の生成と画像評価は行いません。商品画像は取得します。
                  </Note>
                )}
                {["failed", "expired", "cancelled"].includes(stage) && (
                  <p role="alert">
                    {view?.message}
                    {stage === "expired" && view?.canSkipImages
                      ? " 画像なしで最終確認へ進めます。"
                      : ""}
                  </p>
                )}
                <Actions
                  left={
                    <div {...stylex.props(layout.imageRow)}>
                      {back}
                      {view?.referenceRemaining !== undefined &&
                        view.imageMode !== "off" && (
                          <Button
                            disabled={
                              busy || !view.canRegenerate || invalidPrompts
                            }
                            onClick={() => setModal("regenerate")}
                          >
                            作り直す
                          </Button>
                        )}
                      {view?.canRegenerateComparisons && (
                        <Button
                          disabled={busy || referenceDirty || invalidPrompts}
                          onClick={() => setModal("regenerate_comparisons")}
                        >
                          比較画像を再生成
                        </Button>
                      )}
                    </div>
                  }
                >
                  {view?.canSkipImages && skip}
                  {stage === "reference" && (
                    <Button
                      variant="primary"
                      disabled={busy || referenceDirty || invalidPrompts}
                      onClick={() =>
                        void execute(
                          "comparison",
                          prompts ? { prompts: prompts.comparison } : {},
                        )
                      }
                    >
                      了承して生成
                    </Button>
                  )}
                  {stage === "comparison" && (
                    <Button
                      variant="primary"
                      disabled={busy || referenceDirty || comparisonDirty}
                      onClick={() => void execute("final")}
                    >
                      最終確認へ
                    </Button>
                  )}
                  {stage === "failed" &&
                    !view?.canSkipImages &&
                    view?.canRevise && (
                      <Button
                        variant="primary"
                        disabled={busy}
                        onClick={() =>
                          void execute("revise", { source: view.input })
                        }
                      >
                        再試行
                      </Button>
                    )}
                  {stage === "final" && (
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() => void execute("search")}
                    >
                      検索
                    </Button>
                  )}
                </Actions>
              </section>
            )}
          {!editing && !showResults && researching && (
            <>
              <div {...stylex.props(layout.twoColumns)}>
                <div {...stylex.props(layout.stack)}>
                  <p role="status">
                    {stage === "complete"
                      ? "すべての工程が完了しました。結果を確認できます。"
                      : view?.cancelRequested
                        ? "中止を受け付けました。進行中の取得が終了するまでお待ちください。"
                        : "商品の取得と比較を進めています。"}
                  </p>
                  <ResearchProgress
                    current={
                      stage === "complete" ? 5 : (view?.researchStep ?? 0)
                    }
                  />
                </div>
                <aside {...stylex.props(layout.panel)}>
                  <SavedConditions view={view!} />
                </aside>
              </div>
              {stage === "attributes" && (
                <section {...stylex.props(layout.panel, layout.stack)}>
                  <h3>商品の条件を確認</h3>
                  <Note>未確定の条件に対応する商品属性を選んでください。</Note>
                  {view?.unresolved?.map((condition, index) => (
                    <label key={condition} {...stylex.props(layout.field)}>
                      未確定の条件 {index + 1}
                      <select
                        value={selections[condition] ?? ""}
                        onChange={(e) =>
                          setSelections({
                            ...selections,
                            [condition]: e.target.value,
                          })
                        }
                        {...stylex.props(layout.select)}
                      >
                        <option value="">選択してください</option>
                        {view.options
                          ?.filter((o) => o.conditions.includes(condition))
                          .map((o) => (
                            <option key={o.id} value={o.id}>
                              {o.label}
                            </option>
                          ))}
                      </select>
                    </label>
                  ))}
                  <Actions>
                    <Button
                      variant="primary"
                      disabled={
                        busy || !view?.unresolved?.every((c) => selections[c])
                      }
                      onClick={() => void execute("rank", { selections })}
                    >
                      条件を確定
                    </Button>
                  </Actions>
                </section>
              )}
              <Actions
                left={
                  stage === "working" && (
                    <Button
                      variant="danger"
                      disabled={!view?.canCancel || pending}
                      onClick={() => setModal("cancel")}
                    >
                      検索を中止
                    </Button>
                  )
                }
              >
                <Button
                  variant="primary"
                  disabled={stage !== "complete"}
                  onClick={() => {
                    setShowResults(true);
                    window.scrollTo(0, 0);
                  }}
                >
                  結果を見る
                </Button>
              </Actions>
            </>
          )}
          {showResults && <ConnectedProducts view={view!} />}
          <footer {...stylex.props(layout.footer)}>
            <span>Amazon Explorer</span>
            <span>
              {offline
                ? "オフラインモック"
                : view?.mode === "fixture"
                  ? "オフライン接続テスト"
                  : "商品検索"}
            </span>
          </footer>
        </main>
      </div>
      {image !== null && !historyOpen && !modal && (
        <Dialog
          title={image === 0 ? "参考画像" : "比較画像"}
          onClose={() => setImage(null)}
        >
          <img
            src={images[image]}
            alt={image === 0 ? "参考画像" : "比較画像"}
            {...stylex.props(layout.lightbox)}
          />
          <Actions
            left={
              images.length > 1 && (
                <>
                  <Button
                    disabled={image === 0}
                    onClick={() => setImage(image - 1)}
                  >
                    前へ
                  </Button>
                  <Button
                    disabled={image === images.length - 1}
                    onClick={() => setImage(image + 1)}
                  >
                    次へ
                  </Button>
                </>
              )
            }
          >
            <Button data-safe-focus onClick={() => setImage(null)}>
              閉じる
            </Button>
          </Actions>
        </Dialog>
      )}
      {modal && (
        <Dialog
          title={
            modal === "regenerate_comparisons"
              ? "比較画像を再生成"
              : modal === "regenerate"
                ? "参考画像を作り直す"
                : modal === "cancel"
                  ? "検索を中止しますか？"
                  : "保存されていない結果を破棄しますか？"
          }
          onClose={() => setModal(null)}
        >
          <p>
            {modal === "regenerate_comparisons"
              ? "参考画像を再利用して、編集した指示で比較画像を作り直します。"
              : modal === "regenerate"
                ? "参考画像1枚を作り直します。作成済みの比較画像も取り消されます。"
                : modal === "cancel"
                  ? "進行中の取得が終わった時点で停止し、その後の比較・保存を行いません。"
                  : "この結果は履歴に残りません。保存を再試行することもできます。"}
          </p>
          {(modal === "regenerate" || modal === "regenerate_comparisons") && (
            <Note>
              現在：残り{view?.referenceRemaining}回 · 実行後：残り
              {Math.max(0, (view?.referenceRemaining ?? 0) - 1)}回
            </Note>
          )}
          <Actions>
            <Button data-safe-focus onClick={() => setModal(null)}>
              キャンセル
            </Button>
            <Button
              variant={
                modal === "regenerate" || modal === "regenerate_comparisons"
                  ? "primary"
                  : "danger"
              }
              disabled={
                pending ||
                (modal === "regenerate" &&
                  (!view?.canRegenerate || invalidPrompts)) ||
                (modal === "regenerate_comparisons" &&
                  (!view?.canRegenerateComparisons ||
                    referenceDirty ||
                    invalidPrompts)) ||
                (modal === "cancel" && !view?.canCancel)
              }
              onClick={() => {
                const next = modal;
                setModal(null);
                void execute(
                  next === "regenerate_comparisons"
                    ? "regenerate_comparisons"
                    : next === "regenerate"
                      ? "regenerate"
                      : next === "cancel"
                        ? "cancel"
                        : "reset",
                  prompts && next === "regenerate"
                    ? { prompt: prompts.reference }
                    : prompts && next === "regenerate_comparisons"
                      ? { prompts: prompts.comparison }
                      : {},
                );
              }}
            >
              {modal === "regenerate" || modal === "regenerate_comparisons"
                ? "作り直す"
                : modal === "cancel"
                  ? "中止する"
                  : "破棄して新しく検索"}
            </Button>
          </Actions>
        </Dialog>
      )}
    </>
  );
}
