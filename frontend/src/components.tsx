import * as stylex from "@stylexjs/stylex";
import {
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { theme } from "./theme.stylex";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "basic" | "primary" | "danger";
  size?: "regular" | "compact";
};

export function Button({
  variant = "basic",
  size = "regular",
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      {...stylex.props(
        styles.button,
        size === "compact" && styles.compact,
        variant === "primary" && styles.primary,
        variant === "danger" && styles.danger,
      )}
    />
  );
}

export function DeleteButton(props: Omit<ButtonProps, "variant" | "children">) {
  return (
    <Button {...props} variant="danger">
      削除
    </Button>
  );
}

export function Toggle({
  label,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label {...stylex.props(styles.toggleLabel)}>
      <span {...stylex.props(styles.toggleControl)}>
        <input
          type="checkbox"
          role="switch"
          aria-label={label}
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          data-testid="toggle-track"
          {...stylex.props(styles.toggleTrack)}
        />
        <svg
          aria-hidden="true"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          data-testid="toggle-thumb"
          {...stylex.props(styles.toggleThumb, checked && styles.toggleOn)}
        >
          <circle cx="12" cy="12" r="12" fill={theme.white} />
        </svg>
      </span>
      <span {...stylex.props(styles.labelWithIcon)}>
        <img src="/icons/wi-stars.svg" alt="" width={30} height={30} />
        {label}
      </span>
    </label>
  );
}

function CircleFrame({ size, fill }: { size: 28 | 36 | 44; fill: string }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      shapeRendering="geometricPrecision"
      data-testid="progress-ring"
      {...stylex.props(styles.circleFrame)}
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={size / 2 - 1}
        fill={fill}
        stroke={theme.white}
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <div {...stylex.props(styles.note)}>{children}</div>;
}

export function Actions({
  left,
  children,
}: {
  left?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(styles.actions)}>
      <div {...stylex.props(styles.actionGroup)}>{left}</div>
      <div {...stylex.props(styles.actionGroup)}>{children}</div>
    </div>
  );
}

export const STAGES = ["条件整理", "参考画像", "最終確認", "商品調査", "結果"];

export function Stepper({ current }: { current: number }) {
  return (
    <nav aria-label="検索の段階" {...stylex.props(styles.stepper)}>
      <ol {...stylex.props(styles.stepList)}>
        {STAGES.map((label, index) => (
          <li
            key={label}
            aria-current={index === current ? "step" : undefined}
            {...stylex.props(styles.step)}
          >
            {index > 0 && (
              <span
                aria-hidden="true"
                {...stylex.props(
                  styles.track,
                  index <= current && styles.traversed,
                )}
              />
            )}
            <span aria-hidden="true" {...stylex.props(styles.marker)}>
              <CircleFrame
                size={index === current ? 44 : 28}
                fill={index <= current ? theme.blue : theme.black}
              />
              <span {...stylex.props(styles.iconContent)}>
                {index === current ? (
                  <span {...stylex.props(styles.person)}>
                    <span {...stylex.props(styles.personHead)} />
                    <span {...stylex.props(styles.personBody)} />
                  </span>
                ) : (
                  <span {...stylex.props(styles.markerDot)} />
                )}
              </span>
            </span>
            <span {...stylex.props(styles.stepLabel)}>{label}</span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function Dots({ label }: { label: string }) {
  const [dots, setDots] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(
      () => setDots((value) => (value + 1) % 4),
      500,
    );
    return () => window.clearInterval(timer);
  }, []);
  return (
    <span aria-label={label}>
      <span aria-hidden="true">
        {label}
        {".".repeat(dots)}
      </span>
    </span>
  );
}

export function Generating({ label }: { label: string }) {
  return (
    <figure {...stylex.props(styles.imageCard)}>
      <figcaption>{label}</figcaption>
      <div
        role="status"
        aria-label={`${label}を生成中`}
        {...stylex.props(styles.generating)}
      >
        <div data-testid="generation-wave" {...stylex.props(styles.wave)} />
        <span {...stylex.props(styles.pop)}>
          <Dots label="生成中" />
        </span>
      </div>
      <p {...stylex.props(styles.small)}>合成画像の表示を準備しています</p>
    </figure>
  );
}

export function ImageZoom({
  label,
  onOpen,
  children,
}: {
  label: string;
  onOpen: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`${label}を拡大`}
      aria-haspopup="dialog"
      {...stylex.props(styles.imageTrigger, stylex.defaultMarker())}
    >
      {children}
      <span
        aria-hidden="true"
        data-testid="zoom-icon"
        {...stylex.props(styles.zoomIcon)}
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <circle cx="10" cy="10" r="6" stroke="currentColor" strokeWidth="2" />
          <path
            d="m14.5 14.5 6 6M7 10h6M10 7v6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </span>
    </button>
  );
}

export function ImageCard({
  src,
  label,
  detail,
  onOpen,
}: {
  src: string;
  label: string;
  detail?: string;
  onOpen: () => void;
}) {
  return (
    <figure {...stylex.props(styles.imageCard)}>
      <figcaption>{label}</figcaption>
      <ImageZoom label={label} onOpen={onOpen}>
        <img
          src={src}
          alt={label}
          width={256}
          height={180}
          {...stylex.props(styles.previewImage)}
        />
      </ImageZoom>
      <p {...stylex.props(styles.small)}>{detail}</p>
      <p {...stylex.props(styles.small)}>AI生成イメージのモック</p>
    </figure>
  );
}

export const RESEARCH_STAGES = [
  "商品候補を取得",
  "商品情報を整理",
  "商品の特徴を確認",
  "希望条件と比較",
  "結果を準備",
];

export function ResearchProgress({ current }: { current: number }) {
  return (
    <ol aria-label="商品調査の進行" {...stylex.props(styles.researchList)}>
      {RESEARCH_STAGES.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li
            key={label}
            aria-current={active ? "step" : undefined}
            {...stylex.props(styles.researchRow, active && styles.activeRow)}
          >
            <span
              aria-hidden="true"
              {...stylex.props(
                styles.researchIcon,
                (done || active) && styles.filledIcon,
              )}
            >
              <CircleFrame
                size={36}
                fill={done || active ? theme.white : theme.black}
              />
              <span {...stylex.props(styles.iconContent)}>
                {done ? (
                  <span {...stylex.props(styles.researchCheck)}>✓</span>
                ) : active ? (
                  <span
                    data-testid="research-pulse"
                    {...stylex.props(styles.pulse)}
                  />
                ) : (
                  index + 1
                )}
              </span>
            </span>
            <div {...stylex.props(styles.researchText)}>{label}</div>
            <span {...stylex.props(styles.small)}>
              {done ? "完了" : active ? <Dots label="処理中" /> : "待機"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const opener = document.activeElement as HTMLElement | null;
    const previous = document.body.style.overflow;
    dialog?.showModal();
    document.body.style.overflow = "hidden";
    dialog?.querySelector<HTMLElement>("[data-safe-focus]")?.focus();
    return () => {
      dialog?.close();
      document.body.style.overflow = previous;
      opener?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby="dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      {...stylex.props(styles.dialog)}
    >
      <h3 id="dialog-title">{title}</h3>
      {children}
    </dialog>
  );
}

const wave = stylex.keyframes({
  "0%": { transform: "translate(85%, -85%)" },
  "100%": { transform: "translate(-85%, 85%)" },
});
const pulse = stylex.keyframes({
  "0%": { transform: "scale(0.6)" },
  "50%": { transform: "scale(1)" },
  "100%": { transform: "scale(0.6)" },
});
const styles = stylex.create({
  button: {
    width: theme.buttonWidth,
    minWidth: theme.buttonWidth,
    height: theme.buttonHeight,
    paddingBlock: 11,
    paddingInline: 13,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: 100,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
    fontSize: 16,
    fontWeight: 500,
    lineHeight: "24px",
    whiteSpace: "nowrap",
    cursor: { default: "pointer", ":disabled": "not-allowed" },
    color: theme.white,
    backgroundColor: {
      default: theme.black,
      ":hover:not(:disabled)": theme.hover,
    },
  },
  compact: {
    width: theme.compactButtonWidth,
    minWidth: theme.compactButtonWidth,
    height: theme.compactButtonHeight,
    paddingBlock: 5,
    fontSize: 14,
    lineHeight: "24px",
  },
  primary: {
    backgroundColor: {
      default: theme.white,
      ":hover:not(:disabled)": theme.black,
    },
    color: { default: theme.black, ":hover:not(:disabled)": theme.white },
  },
  danger: {
    boxShadow: `inset 0 0 0 1px ${theme.dangerBorder}, inset 0 0 0 1px ${theme.dangerBorder}`,
    color: theme.dangerBorder,
  },
  toggleLabel: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginTop: 24,
    width: "fit-content",
  },
  toggleControl: {
    width: 56,
    height: 32,
    position: "relative",
    flexShrink: 0,
  },
  toggleTrack: {
    appearance: "none",
    display: "block",
    width: 56,
    height: 32,
    margin: 0,
    borderWidth: 0,
    borderRadius: 100,
    backgroundColor: { default: theme.hover, ":checked": theme.blue },
    transitionProperty: "background-color",
    transitionDuration: {
      default: "240ms",
      "@media (prefers-reduced-motion: reduce)": "0s",
    },
    transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
    cursor: { default: "pointer", ":disabled": "not-allowed" },
  },
  toggleThumb: {
    position: "absolute",
    top: 4,
    left: 4,
    display: "block",
    pointerEvents: "none",
    transform: "translateX(0px)",
    transitionProperty: "transform",
    transitionDuration: {
      default: "240ms",
      "@media (prefers-reduced-motion: reduce)": "0s",
    },
    transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
  },
  toggleOn: { transform: "translateX(24px)" },
  circleFrame: {
    position: "absolute",
    inset: 0,
    margin: "auto",
    display: "block",
    pointerEvents: "none",
  },
  iconContent: {
    position: "relative",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  note: {
    backgroundColor: theme.note,
    padding: 20,
    borderRadius: theme.radius,
    fontSize: 14,
    lineHeight: "24px",
  },
  small: { fontSize: 14, lineHeight: "24px" },
  actions: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 32,
    marginTop: 32,
  },
  actionGroup: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
  },
  stepper: { marginTop: 36, marginBottom: 44 },
  stepList: {
    padding: 0,
    margin: 0,
    display: "grid",
    gridTemplateColumns: "repeat(5, 1fr)",
    listStyle: "none",
  },
  step: {
    position: "relative",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 10,
  },
  track: {
    height: 2,
    position: "absolute",
    top: 21,
    right: "50%",
    width: "100%",
    backgroundColor: theme.white,
  },
  traversed: { backgroundColor: theme.blue },
  marker: {
    width: 44,
    height: 44,
    position: "relative",
    zIndex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  markerDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    backgroundColor: theme.white,
  },
  stepLabel: { fontSize: 14, lineHeight: "24px" },
  person: { width: 22, height: 26, position: "relative" },
  personHead: {
    position: "absolute",
    width: 10,
    height: 10,
    top: 1,
    left: 6,
    borderRadius: "50%",
    backgroundColor: theme.white,
  },
  personBody: {
    position: "absolute",
    width: 22,
    height: 12,
    bottom: 0,
    left: 0,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    backgroundColor: theme.white,
  },
  imageCard: {
    width: 256,
    padding: 17,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
    flexShrink: 0,
  },
  imageTrigger: {
    position: "relative",
    display: "block",
    width: "100%",
    padding: 0,
    borderWidth: 0,
    borderRadius: theme.radius,
    backgroundColor: "transparent",
    cursor: "zoom-in",
  },
  zoomIcon: {
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    width: 44,
    height: 44,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "50%",
    color: theme.white,
    backgroundColor: theme.black,
    pointerEvents: "none",
    opacity: {
      default: 0,
      [stylex.when.ancestor(":hover")]: 1,
      [stylex.when.ancestor(":focus-visible")]: 1,
    },
  },
  previewImage: {
    width: "100%",
    height: 180,
    objectFit: "contain",
    borderRadius: theme.radius,
  },
  generating: {
    width: "100%",
    height: 180,
    position: "relative",
    overflow: "hidden",
    backgroundColor: theme.hover,
    borderRadius: theme.radius,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  wave: {
    position: "absolute",
    inset: "-50%",
    backgroundImage:
      "linear-gradient(45deg, transparent 35%, #ffffff 50%, transparent 65%)",
    opacity: 0.25,
    animationName: wave,
    animationDuration: "1.5s",
    animationIterationCount: "infinite",
    animationTimingFunction: "linear",
  },
  pop: {
    zIndex: 1,
    paddingBlock: 6,
    paddingInline: 12,
    fontSize: 14,
    lineHeight: "20px",
    textAlign: "center",
    backgroundColor: theme.black,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    minWidth: 96,
  },
  researchList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  researchRow: {
    display: "flex",
    alignItems: "center",
    gap: 20,
    padding: 25,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
  },
  activeRow: { backgroundColor: theme.hover },
  researchIcon: {
    width: 36,
    height: 36,
    position: "relative",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  filledIcon: { color: theme.black },
  researchCheck: { fontSize: 24, lineHeight: "24px", fontWeight: 700 },
  researchText: { flexGrow: 1 },
  pulse: {
    width: 18,
    height: 18,
    borderRadius: "50%",
    backgroundColor: theme.blue,
    animationName: pulse,
    animationDuration: "1.5s",
    animationIterationCount: "infinite",
    animationTimingFunction: "ease-in-out",
  },
  dialog: {
    backgroundColor: theme.black,
    color: theme.white,
    borderWidth: 0,
    boxShadow: `inset 0 0 0 1px ${theme.white}, inset 0 0 0 1px ${theme.white}`,
    borderRadius: theme.radius,
    padding: 33,
    width: 760,
    maxHeight: "90vh",
    overflowY: "auto",
    "::backdrop": { backgroundColor: theme.black, opacity: 0.8 },
  },
  labelWithIcon: {
    display: "inline-flex",
    alignItems: "center",
    gap: 3,
  },
});
