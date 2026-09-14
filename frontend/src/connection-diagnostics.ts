const CODES = [
  "network",
  "timeout",
  "aborted",
  "http",
  "json",
  "schema",
  "unknown",
] as const;
export type ConnectionCode = (typeof CODES)[number];
export type ConnectionOperation = "state" | "command";
export const MAX_CONNECTION_DIAGNOSTICS = 10;
export const CONNECTION_TIMEOUT_MS = 10_000;
const MAX_DIAGNOSTIC_DURATION_MS = 86_400_000;
const STORAGE_KEY = "amazon-explorer.connection-diagnostics.v1";

const VALIDATION_REASONS: Record<string, string> = {
  "Invalid search response": "応答の型",
  "Invalid ranking profile": "採点方式",
  "Invalid editable terms": "商品名・条件",
  "Invalid editing state": "編集状態",
  "Invalid condition labels": "条件ラベル",
  "Invalid condition interpretation": "条件の解釈",
  "Invalid saved history content": "履歴内容",
  "Invalid progress": "進捗",
  "Invalid operation": "処理の種類",
  "Invalid image prompts": "画像指示",
  "Invalid image mode": "画像モード",
  "Image-free search contains image evidence": "画像なし状態との矛盾",
  "Missing search content": "必須データの欠落",
  "Invalid search state": "段階・更新番号",
  "Invalid server instance": "サーバー識別子",
  "Invalid search list": "検索リスト",
  "Invalid search text": "表示文の形式",
  "Invalid preview source": "画像の形式",
  "Invalid condition options": "条件の選択肢",
  "Invalid search products": "商品の形式",
};

export interface ConnectionDiagnostic {
  code: ConnectionCode;
  operation: ConnectionOperation;
  occurredAt: string;
  elapsedMs: number;
  httpStatus: number | null;
  validation: string | null;
}

export function validationReason(error: unknown): string | null {
  return error instanceof Error &&
    Object.hasOwn(VALIDATION_REASONS, error.message)
    ? error.message
    : null;
}

export function describeConnectionError(
  diagnostic: ConnectionDiagnostic,
): string {
  switch (diagnostic.code) {
    case "timeout":
      return `応答待ちが${CONNECTION_TIMEOUT_MS / 1000}秒を超えました（timeout）。`;
    case "network":
      return "通信に失敗しました（network）。";
    case "aborted":
      return "通信が中断されました（aborted）。";
    case "http":
      return `サーバーがHTTP ${diagnostic.httpStatus}を返しました（http）。`;
    case "json":
      return "応答をJSONとして読み取れませんでした（json）。";
    case "schema":
      return `応答データの検証に失敗しました（schema：${diagnostic.validation ? VALIDATION_REASONS[diagnostic.validation] : "未分類"}）。`;
    default:
      return "未分類のエラーが発生しました（unknown）。";
  }
}

export class ConnectionError extends Error {
  readonly diagnostic: ConnectionDiagnostic;

  constructor(
    code: ConnectionCode,
    operation: ConnectionOperation,
    elapsedMs: number,
    httpStatus: number | null = null,
    validation: string | null = null,
  ) {
    const diagnostic = {
      code,
      operation,
      occurredAt: new Date().toISOString(),
      elapsedMs: Math.min(
        MAX_DIAGNOSTIC_DURATION_MS,
        Math.max(0, Math.round(elapsedMs)),
      ),
      httpStatus,
      validation,
    };
    super(describeConnectionError(diagnostic));
    this.diagnostic = diagnostic;
  }
}

function safeDiagnostic(value: unknown): ConnectionDiagnostic | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const row = value as ConnectionDiagnostic;
  if (
    !CODES.includes(row.code) ||
    !["state", "command"].includes(row.operation) ||
    typeof row.occurredAt !== "string" ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(row.occurredAt) ||
    !Number.isFinite(Date.parse(row.occurredAt)) ||
    !Number.isInteger(row.elapsedMs) ||
    row.elapsedMs < 0 ||
    row.elapsedMs > MAX_DIAGNOSTIC_DURATION_MS ||
    (row.httpStatus !== null &&
      (!Number.isInteger(row.httpStatus) ||
        row.httpStatus < 100 ||
        row.httpStatus > 599)) ||
    (row.validation !== null &&
      (typeof row.validation !== "string" ||
        !Object.hasOwn(VALIDATION_REASONS, row.validation)))
  ) {
    return null;
  }
  // Rebuild the allowlisted fields; never retain extra exception or payload fields.
  return {
    code: row.code,
    operation: row.operation,
    occurredAt: row.occurredAt,
    elapsedMs: row.elapsedMs,
    httpStatus: row.httpStatus,
    validation: row.validation,
  };
}

export function connectionDiagnostic(
  error: unknown,
  operation: ConnectionOperation,
): ConnectionDiagnostic {
  if (error instanceof ConnectionError) {
    const diagnostic = safeDiagnostic(error.diagnostic);
    if (diagnostic && diagnostic.operation === operation) {
      return diagnostic;
    }
  }
  return new ConnectionError("unknown", operation, 0).diagnostic;
}

export function loadConnectionDiagnostics(): ConnectionDiagnostic[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw || raw.length > 16_384) {
      return [];
    }
    const rows: unknown = JSON.parse(raw);
    if (!Array.isArray(rows)) {
      return [];
    }
    return rows
      .slice(-MAX_CONNECTION_DIAGNOSTICS)
      .map(safeDiagnostic)
      .filter((row) => row !== null);
  } catch {
    return []; // Browser storage can be unavailable; requests must still work.
  }
}

export function saveConnectionDiagnostics(rows: ConnectionDiagnostic[]): void {
  const safe = rows
    .slice(-MAX_CONNECTION_DIAGNOSTICS)
    .map(safeDiagnostic)
    .filter((row) => row !== null);
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
  } catch {
    // The mounted screen retains diagnostics even if browser storage is blocked.
  }
}
