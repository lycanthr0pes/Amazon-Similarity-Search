import * as stylex from "@stylexjs/stylex";
import { useEffect, useRef, useState } from "react";
import { Actions, Button, Dialog, Note, ImageCard } from "./components";
import { layout } from "./screens";
import { SavedConditions } from "./ConnectedConditions";
import { ConnectedProducts } from "./ConnectedProducts";
import { formatHistoryDate as date } from "./history-date";
import {
  historyProductName,
  HistoryUnavailable,
  type HistoryItem,
  type HistoryDetail,
} from "./connected-history-api";

import { useSearchClient } from "./search-client";

export function ConnectedHistory() {
  const {
    readHistoryState,
    readHistoryDetail,
    deleteHistory,
    purgeExpiredHistory,
    offline,
  } = useSearchClient();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [id, setId] = useState(
    location.hash.startsWith("#history/") ? location.hash.slice(9) : "",
  );
  const [image, setImage] = useState<number | null>(null);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [reload, setReload] = useState(0);
  const [target, setTarget] = useState<HistoryItem | null>(null);
  const [deleting, setDeleting] = useState<Set<string>>(new Set());
  const [deleteErrors, setDeleteErrors] = useState<Record<string, boolean>>({});
  const [cleanupPending, setCleanupPending] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const inflight = useRef(new Set<string>());
  const removed = useRef(new Set<string>());
  const currentId = useRef(id);
  currentId.current = id;
  const heading = useRef<HTMLHeadingElement>(null);
  const scroll = useRef(0);
  useEffect(() => {
    const update = () =>
      setId(
        location.hash.startsWith("#history/") ? location.hash.slice(9) : "",
      );
    addEventListener("hashchange", update);
    return () => removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    setDetail(null);
    const load = async () => {
      try {
        if (id) {
          const saved = await readHistoryDetail(id);
          if (active && !removed.current.has(saved.id)) setDetail(saved);
        } else {
          const state = await readHistoryState();
          if (active) {
            setItems(
              state.items.filter((item) => !removed.current.has(item.id)),
            );
            setCleanupPending(state.cleanupPending);
          }
        }
      } catch (e) {
        if (active)
          setError(
            e instanceof HistoryUnavailable
              ? "この検索履歴は保存期間が終了したか、見つかりませんでした"
              : "検索履歴を読み込めませんでした",
          );
      } finally {
        if (active) {
          setBusy(false);
          if (!id)
            requestAnimationFrame(() => window.scrollTo(0, scroll.current));
        }
      }
    };
    void load();
    heading.current?.focus({ preventScroll: true });
    return () => {
      active = false;
    };
  }, [id, reload, readHistoryState, readHistoryDetail]);
  function open(next: string) {
    if (next) scroll.current = window.scrollY;
    history.replaceState(
      null,
      "",
      location.pathname +
        location.search +
        "#history" +
        (next ? "/" + next : ""),
    );
    setId(next);
    if (next) window.scrollTo(0, 0);
  }
  async function remove(item: HistoryItem) {
    if (inflight.current.has(item.id) || removed.current.has(item.id)) return;
    inflight.current.add(item.id);
    setDeleting(new Set(inflight.current));
    setTarget(null);
    setDeleteErrors((previous) => ({ ...previous, [item.id]: false }));
    try {
      await deleteHistory(item.id);
      removed.current.add(item.id);
      setItems((previous) => previous.filter((row) => row.id !== item.id));
      if (currentId.current === item.id) open("");
    } catch {
      setDeleteErrors((previous) => ({ ...previous, [item.id]: true }));
    } finally {
      inflight.current.delete(item.id);
      setDeleting(new Set(inflight.current));
    }
  }
  function deletionStatus(item: HistoryItem) {
    return (
      <>
        {deleting.has(item.id) && <p role="status">削除しています</p>}
        {deleteErrors[item.id] && (
          <div>
            <p role="alert">履歴を削除できませんでした</p>
            <Button
              onClick={() => void remove(item)}
              disabled={deleting.has(item.id)}
            >
              再試行
            </Button>
          </div>
        )}
      </>
    );
  }
  async function retryCleanup() {
    if (cleaning) return;
    setCleaning(true);
    try {
      await purgeExpiredHistory();
      setCleanupPending(false);
      setReload((value) => value + 1);
    } catch {
      setCleanupPending(true);
    } finally {
      setCleaning(false);
    }
  }
  return (
    <main {...stylex.props(layout.page, layout.historyPage)}>
      <div {...stylex.props(layout.intro)}>
        <p {...stylex.props(layout.eyebrow)}>SAVED SEARCHES</p>
        <h1 ref={heading} tabIndex={-1}>
          {id ? "保存した検索結果" : "検索履歴"}
        </h1>
      </div>
      <div {...stylex.props(layout.stack)}>
        {id && !detail && (
          <Actions>
            <Button onClick={() => open("")}>履歴へ戻る</Button>
          </Actions>
        )}
        {error && (
          <p role="alert" {...stylex.props(layout.error)}>
            {error}
          </p>
        )}
        {busy && <p role="status">履歴を読み込んでいます</p>}
        {cleanupPending && (
          <div>
            <p role="alert">
              {offline
                ? "期限切れデータを削除できませんでした。このタブを開いている間は自動で再試行します。"
                : "期限切れデータを削除できませんでした。サーバーは自動で再試行します。"}
            </p>
            <Button disabled={cleaning} onClick={() => void retryCleanup()}>
              期限切れ削除を再試行
            </Button>
          </div>
        )}
        {(offline || !id) && (
          <Note>
            {offline
              ? "オフラインモック · 固定の合成結果を、このタブで最大30日間保存します。最新30件を表示し、タブを閉じると消えます。再読込で検索は再実行しません。"
              : "完了した検索を30日間保存します。最新30件を表示し、再読込で検索は再実行しません。"}
          </Note>
        )}
        {!id && (
          <>
            {!busy && !error && items.length === 0 && (
              <section {...stylex.props(layout.panel)}>
                <h2>保存された検索結果はまだありません</h2>
                <p>完了した結果をここから見直せます。</p>
              </section>
            )}
            <ul
              aria-label="検索履歴一覧"
              {...stylex.props(layout.resultGrid, layout.historyGrid)}
            >
              {items.map((item) => (
                <li
                  key={item.id}
                  {...stylex.props(layout.product, layout.historyCard)}
                >
                  <p {...stylex.props(layout.small)}>
                    {date(item.completedAt)} から {date(item.expiresAt)}まで保存
                  </p>
                  <h4 {...stylex.props(layout.inputText)}>
                    {historyProductName(item)}
                  </h4>
                  <p>比較件数：{item.count}件</p>

                  <Actions
                    left={
                      <Button
                        variant="danger"
                        size="compact"
                        disabled={busy || deleting.has(item.id)}
                        onClick={() => setTarget(item)}
                      >
                        削除
                      </Button>
                    }
                  >
                    <Button
                      variant="primary"
                      size="compact"
                      disabled={busy || deleting.has(item.id)}
                      onClick={() => open(item.id)}
                    >
                      開く
                    </Button>
                  </Actions>
                  {deletionStatus(item)}
                </li>
              ))}
            </ul>
          </>
        )}
        {detail && (
          <>
            <section {...stylex.props(layout.panel, layout.stack)}>
              <h2>
                {detail.view.historyContentAvailable
                  ? "保存された検索内容"
                  : "入力した文章"}
              </h2>
              <p {...stylex.props(historyStyles.source)}>
                {detail.view.historyContentAvailable
                  ? detail.view.input
                  : detail.summary}
              </p>
              {detail.view.historyContentAvailable && (
                <SavedConditions
                  view={detail.view}
                  cards
                  includeInput={false}
                />
              )}
              <p>
                {date(detail.completedAt)} から {date(detail.expiresAt)}まで保存
              </p>
              <Actions
                left={
                  <Button
                    variant="danger"
                    disabled={deleting.has(detail.id)}
                    onClick={() => setTarget(detail)}
                  >
                    削除
                  </Button>
                }
              >
                <Button onClick={() => open("")}>履歴へ戻る</Button>
              </Actions>
              {deletionStatus(detail)}
            </section>
            {detail.view.imageMode === "off" ? (
              <p>画像比較なしで保存された結果です。</p>
            ) : (
              <details>
                <summary>保存された参考画像・比較画像</summary>
                <div {...stylex.props(layout.imageGallery)}>
                  {detail.view.images?.map((src, i) => (
                    <ImageCard
                      key={i}
                      src={src}
                      label={
                        i === 0
                          ? "保存された参考画像"
                          : `保存された比較画像${i}`
                      }
                      onOpen={() => setImage(i)}
                      imageKind={offline ? "mock" : "generated"}
                    />
                  ))}
                </div>
              </details>
            )}
            <ConnectedProducts view={detail.view} historical />
          </>
        )}
      </div>
      <footer {...stylex.props(layout.footer)}>
        <span>Amazon Explorer</span>
        <span>検索履歴</span>
      </footer>
      {image !== null && detail && !target && (
        <Dialog
          title={image === 0 ? "保存された参考画像" : "保存された比較画像"}
          onClose={() => setImage(null)}
        >
          <img
            src={detail.view.images?.[image]}
            alt={image === 0 ? "保存された参考画像" : "保存された比較画像"}
            {...stylex.props(layout.lightbox)}
          />
          <Actions
            left={
              <>
                <Button
                  disabled={image === 0}
                  onClick={() => setImage(image - 1)}
                >
                  前へ
                </Button>
                <Button
                  disabled={image >= (detail.view.images?.length ?? 0) - 1}
                  onClick={() => setImage(image + 1)}
                >
                  次へ
                </Button>
              </>
            }
          >
            <Button data-safe-focus onClick={() => setImage(null)}>
              閉じる
            </Button>
          </Actions>
        </Dialog>
      )}
      {target && (
        <Dialog
          title="この履歴を削除しますか？"
          onClose={() => setTarget(null)}
        >
          <p>{date(target.completedAt)}</p>
          <p>{historyProductName(target)}</p>
          <p>
            この検索の保存結果と生成画像を削除します。削除後は復元できません。
          </p>
          <Actions
            left={
              <Button variant="danger" onClick={() => void remove(target)}>
                削除
              </Button>
            }
          >
            <Button data-safe-focus onClick={() => setTarget(null)}>
              キャンセル
            </Button>
          </Actions>
        </Dialog>
      )}
    </main>
  );
}

const historyStyles = stylex.create({
  source: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
});
