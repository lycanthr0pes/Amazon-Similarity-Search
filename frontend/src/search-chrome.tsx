import * as stylex from "@stylexjs/stylex";
import { Button } from "./components";
import { layout } from "./screens";

export function SearchHeader({
  section,
  historyOpen,
  onNew,
  onHistory,
  disabled = false,
}: {
  section: string;
  historyOpen: boolean;
  onNew?: () => void;
  onHistory?: () => void;
  disabled?: boolean;
}) {
  return (
    <header {...stylex.props(layout.header)}>
      <div {...stylex.props(layout.brand)}>
        <span aria-hidden="true" {...stylex.props(layout.monogram)}>
          AE
        </span>
        <div>
          <p {...stylex.props(layout.brandName)}>Amazon Explorer</p>
          <p {...stylex.props(layout.small)}>{section}</p>
        </div>
      </div>
      <div {...stylex.props(layout.headerActions)}>
        {onNew && (
          <Button variant="primary" disabled={disabled} onClick={onNew}>
            新しく検索
          </Button>
        )}
        {onHistory && (
          <Button onClick={onHistory}>
            {historyOpen ? "検索へ戻る" : "検索履歴"}
          </Button>
        )}
      </div>
    </header>
  );
}

export function BackToTop() {
  return (
    <button
      type="button"
      aria-label="トップに戻る"
      title="トップに戻る"
      onClick={() =>
        window.scrollTo({
          top: 0,
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
            .matches
            ? "instant"
            : "smooth",
        })
      }
      {...stylex.props(layout.backToTop)}
    >
      <svg
        aria-hidden="true"
        width="28"
        height="28"
        viewBox="0 0 24 24"
        fill="none"
      >
        <path
          d="M12 20V4m-7 7 7-7 7 7"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
export function ResultCount({
  count,
  onCount,
  maximum = 30,
}: {
  count: number;
  onCount: (value: number) => void;
  maximum?: number;
}) {
  return (
    <label>
      表示件数{" "}
      <select
        aria-label="表示件数"
        value={count}
        onChange={(event) => onCount(Number(event.target.value))}
        {...stylex.props(layout.select)}
      >
        {Array.from({ length: maximum }, (_, i) => (
          <option key={i + 1} value={i + 1}>
            {i + 1}件
          </option>
        ))}
      </select>
    </label>
  );
}
