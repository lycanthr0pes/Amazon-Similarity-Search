import * as stylex from "@stylexjs/stylex";
import type { LanguageScore, ProductScores } from "./connected-api";

const styles = stylex.create({
  wrapper: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 14 },
  cell: {
    padding: "8px 4px",
    borderBottom: "1px solid #606060",
    textAlign: "right",
  },
  heading: { whiteSpace: "nowrap" },
  label: { textAlign: "left" },
});

function points(value: number | null | undefined, negative = false) {
  return value == null ? "—" : ((negative ? -1 : 1) * value * 100).toFixed(1);
}

function ScoreRow({
  label,
  score,
  negative = false,
  showWeight = false,
  weight,
}: {
  label: string;
  score: LanguageScore;
  negative?: boolean;
  showWeight?: boolean;
  weight?: number;
}) {
  return (
    <tr>
      <th scope="row" {...stylex.props(styles.cell, styles.label)}>
        {label}
      </th>
      <td {...stylex.props(styles.cell)}>{points(score.score_ja, negative)}</td>
      <td {...stylex.props(styles.cell)}>{points(score.score_en, negative)}</td>
      <td {...stylex.props(styles.cell)}>{points(score.score, negative)}</td>
      {showWeight && (
        <td {...stylex.props(styles.cell)}>
          {weight === undefined ? "—" : `${weight}倍`}
        </td>
      )}
    </tr>
  );
}

export function ConnectedScores({
  scores,
  labels,
  sortProfile,
  imageMode,
}: {
  scores: ProductScores;
  labels?: Record<string, string>;
  sortProfile?: string | null;
  imageMode?: "off";
}) {
  const dual = sortProfile === "excluded-title-conditions-text-image-review-v2";
  const weighted = scores.conditions.some(
    (condition) => condition.weight !== undefined,
  );
  const negative =
    dual || sortProfile === "excluded-title-conditions-image-review-v1";
  return (
    <>
      <div {...stylex.props(styles.wrapper)}>
        <table aria-label="点数の内訳" {...stylex.props(styles.table)}>
          <thead>
            <tr>
              {[
                "評価項目",
                "日本語",
                "英語",
                "採用点",
                ...(weighted ? ["重み"] : []),
              ].map((label) => (
                <th
                  key={label}
                  scope="col"
                  {...stylex.props(styles.cell, styles.heading)}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <ScoreRow
              label="タイトル一致"
              score={scores.title}
              showWeight={weighted}
            />
            {scores.conditions.map((condition, index) => (
              <ScoreRow
                key={condition.requirement_id}
                label={`${{ required: "優先", preferred: "希望", excluded: "除外" }[condition.strength]}：${labels?.[condition.requirement_id] ?? `条件${index + 1}`}`}
                score={condition}
                showWeight={weighted}
                weight={condition.weight}
                negative={negative && condition.strength === "excluded"}
              />
            ))}
          </tbody>
        </table>
      </div>
      {dual && imageMode !== "off" && (
        <p>
          文章と画像：{points(scores.textImage)}
          {scores.textImage == null ? "（未評価）" : ""}
        </p>
      )}
      {scores.image !== undefined && (
        <p>
          {dual ? "画像同士" : "画像評価"}：
          {imageMode === "off" ? "未使用" : points(scores.image)}
          {imageMode !== "off" && scores.image === null ? "（未評価）" : ""}
        </p>
      )}
      {dual && (
        <p>
          視覚条件は文章と画像の点数を優先し、同点の場合に画像同士の点数を使います。
        </p>
      )}
      {!dual && scores.total !== undefined && imageMode !== "off" && (
        <p>参考合成点：{points(scores.total)}</p>
      )}
    </>
  );
}
