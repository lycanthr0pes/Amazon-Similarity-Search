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
}: {
  label: string;
  score: LanguageScore;
  negative?: boolean;
}) {
  return (
    <tr>
      <th scope="row" {...stylex.props(styles.cell, styles.label)}>
        {label}
      </th>
      <td {...stylex.props(styles.cell)}>{points(score.score_ja, negative)}</td>
      <td {...stylex.props(styles.cell)}>{points(score.score_en, negative)}</td>
      <td {...stylex.props(styles.cell)}>{points(score.score, negative)}</td>
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
  const negative = sortProfile === "excluded-title-conditions-image-review-v1";
  return (
    <>
      <div {...stylex.props(styles.wrapper)}>
        <table aria-label="点数の内訳" {...stylex.props(styles.table)}>
          <thead>
            <tr>
              {["評価項目", "日本語", "英語", "採用点"].map((label) => (
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
            <ScoreRow label="タイトル一致" score={scores.title} />
            {scores.conditions.map((condition, index) => (
              <ScoreRow
                key={condition.requirement_id}
                label={`${{ required: "優先", preferred: "希望", excluded: "除外" }[condition.strength]}：${labels?.[condition.requirement_id] ?? `条件${index + 1}`}`}
                score={condition}
                negative={negative && condition.strength === "excluded"}
              />
            ))}
          </tbody>
        </table>
      </div>
      {scores.image !== undefined && (
        <p>
          画像評価：{imageMode === "off" ? "未使用" : points(scores.image)}
          {imageMode !== "off" && scores.image === null ? "（未評価）" : ""}
        </p>
      )}
      {scores.total !== undefined && imageMode !== "off" && (
        <p>参考合成点：{points(scores.total)}</p>
      )}
    </>
  );
}
