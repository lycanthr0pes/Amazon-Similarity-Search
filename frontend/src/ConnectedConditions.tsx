import * as stylex from "@stylexjs/stylex";
import { layout } from "./screens";
import type { SearchView } from "./connected-api";
import {
  conditionLabels,
  conditionStrengths,
  type ConditionDraft,
} from "./condition-editor";

export function ConditionGroupEditor({
  value,
  onChange,
  readOnly,
}: {
  value: ConditionDraft;
  onChange: (value: ConditionDraft) => void;
  readOnly: boolean;
}) {
  return (
    <div {...stylex.props(layout.stack)}>
      <h3>条件</h3>
      <p id="condition-notation" {...stylex.props(layout.small)}>
        条件は半角カンマ（,）で区切ります。例：丸い形, 3000円以下。
        希望・否定の表現は付けず、各欄に特徴だけを入力してください。
        数字には桁区切りのカンマを使いません。空欄は条件なしです。
      </p>
      <div {...stylex.props(layout.fields)}>
        {conditionStrengths
          .filter((strength) => strength !== "neutral")
          .map((strength) => (
            <label key={strength} {...stylex.props(layout.field)}>
              {conditionLabels[strength]}
              <input
                aria-label={conditionLabels[strength]}
                aria-describedby="condition-notation"
                value={value[strength]}
                readOnly={readOnly}
                onChange={(event) =>
                  onChange({ ...value, [strength]: event.target.value })
                }
                {...stylex.props(layout.input)}
              />
            </label>
          ))}
      </div>
      {value.neutral && (
        <p {...stylex.props(layout.small)}>
          検索に使わない条件：{value.neutral}
        </p>
      )}
    </div>
  );
}

export function SavedConditions({
  view,
  cards = false,
  includeInput = true,
}: {
  view: SearchView;
  cards?: boolean;
  includeInput?: boolean;
}) {
  return (
    <div {...stylex.props(layout.stack)}>
      <h3>確認した条件</h3>
      <dl
        {...stylex.props(layout.definition, cards && layout.definitionColumns)}
      >
        {Boolean(view.conditionReview?.length) &&
          conditionStrengths.map((strength) => (
            <div key={strength}>
              <dt {...stylex.props(layout.small)}>
                {conditionLabels[strength]}
              </dt>
              <dd
                {...stylex.props(
                  layout.definitionValue,
                  cards && layout.inputText,
                )}
              >
                {view.conditionReview
                  ?.filter((row) => row.strength === strength)
                  .map((row) => row.quote)
                  .join(", ") || "なし"}
                {strength === "neutral" && (
                  <span>（検索・採点・画像条件には使用しません）</span>
                )}
              </dd>
            </div>
          ))}
        {!view.conditionReview?.length &&
          Object.entries(view.conditionLabels ?? {}).map(([id, label]) => (
            <div key={id}>
              <dt {...stylex.props(layout.small)}>検索条件</dt>
              <dd
                {...stylex.props(
                  layout.definitionValue,
                  cards && layout.inputText,
                )}
              >
                {label}
              </dd>
            </div>
          ))}
      </dl>
      {includeInput && (
        <details>
          <summary>入力した文章</summary>
          <p {...stylex.props(layout.wrap, cards && layout.inputText)}>
            {view.input}
          </p>
        </details>
      )}
    </div>
  );
}
