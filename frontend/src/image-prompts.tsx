import * as stylex from "@stylexjs/stylex";
import { layout } from "./screens";

import { validPrompts, type ImagePrompts } from "./image-prompt-values";
export { validPrompts, type ImagePrompts } from "./image-prompt-values";

export function ImagePromptEditor({
  value,
  onChange,
  disabled,
  referenceDisabled,
  labels = {},
  referenceOnly = false,
}: {
  value: ImagePrompts;
  onChange: (value: ImagePrompts) => void;
  disabled?: boolean;
  referenceDisabled?: boolean;
  labels?: Record<string, string>;
  referenceOnly?: boolean;
}) {
  return (
    <div {...stylex.props(layout.stack)}>
      <label {...stylex.props(layout.field)}>
        参考画像のプロンプト
        <textarea
          aria-label="参考画像のプロンプト"
          value={value.reference}
          disabled={disabled || referenceDisabled}
          maxLength={12000}
          onChange={(e) => onChange({ ...value, reference: e.target.value })}
          {...stylex.props(layout.input, layout.textarea)}
        />
      </label>
      {!referenceOnly &&
        Object.entries(value.comparison).map(([id, prompt], index) => (
          <label key={id} {...stylex.props(layout.field)}>
            比較画像のプロンプト：{labels[id] ?? `${index + 1}`}
            <textarea
              aria-label={`比較画像のプロンプト：${labels[id] ?? `${index + 1}`}`}
              value={prompt}
              disabled={disabled}
              maxLength={12000}
              onChange={(e) =>
                onChange({
                  ...value,
                  comparison: { ...value.comparison, [id]: e.target.value },
                })
              }
              {...stylex.props(layout.input, layout.textarea)}
            />
          </label>
        ))}
      <p {...stylex.props(layout.small)}>
        画像への指示を編集できます。検索条件や採点条件は変わりません。各12,000文字以内、URLは使用できません。
      </p>
      {!validPrompts(value) && (
        <p role="alert">
          プロンプトを空欄にせず、文字数と使用できる文字を確認してください。
        </p>
      )}
    </div>
  );
}
