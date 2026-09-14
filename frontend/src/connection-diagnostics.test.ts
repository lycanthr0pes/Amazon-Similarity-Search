import { afterEach, expect, it, vi } from "vitest";
import {
  ConnectionError,
  connectionDiagnostic,
  describeConnectionError,
  loadConnectionDiagnostics,
  saveConnectionDiagnostics,
  validationReason,
} from "./connection-diagnostics";

afterEach(() => vi.unstubAllGlobals());

it("retains only ten safe records across reloads and discards extra fields", () => {
  let stored = "";
  vi.stubGlobal("sessionStorage", {
    getItem: () => stored,
    setItem: (_: string, value: string) => {
      stored = value;
    },
  });
  const records = Array.from({ length: 12 }, (_, i) => ({
    ...new ConnectionError("http", "state", i, 503).diagnostic,
    response: "private response",
    input: "private input",
    stack: "private stack",
  }));
  saveConnectionDiagnostics(records);
  const loaded = loadConnectionDiagnostics();
  expect(loaded).toHaveLength(10);
  expect(loaded[0].elapsedMs).toBe(2);
  expect(stored).not.toContain("private");
  expect(describeConnectionError(loaded[0])).toContain("HTTP 503");
});

it("ignores corrupt or unsafe stored diagnostics", () => {
  const valid = new ConnectionError(
    "schema",
    "state",
    1,
    200,
    "Invalid search state",
  ).diagnostic;
  for (const stored of [
    "invalid JSON",
    "null",
    "x".repeat(16_385),
    JSON.stringify([{ ...valid, validation: "private response" }]),
    JSON.stringify([{ ...valid, code: "private code" }]),
    JSON.stringify([{ ...valid, occurredAt: "private timestamp" }]),
    JSON.stringify([{ ...valid, httpStatus: "private status" }]),
    JSON.stringify([{ ...valid, elapsedMs: -1 }]),
  ]) {
    vi.stubGlobal("sessionStorage", { getItem: () => stored });
    expect(loadConnectionDiagnostics()).toEqual([]);
  }
});

it("does not turn unavailable storage into another connection error", () => {
  vi.stubGlobal("sessionStorage", {
    getItem: () => {
      throw new Error("private read failure");
    },
    setItem: () => {
      throw new Error("private write failure");
    },
  });
  expect(loadConnectionDiagnostics()).toEqual([]);
  expect(() =>
    saveConnectionDiagnostics([
      new ConnectionError("network", "state", 1).diagnostic,
    ]),
  ).not.toThrow();
});

it("uses only fixed validation reasons and redacts unknown errors", () => {
  expect(validationReason(new Error("Invalid editable terms"))).toBe(
    "Invalid editable terms",
  );
  expect(validationReason(new Error("private response"))).toBeNull();
  expect(validationReason(new Error("constructor"))).toBeNull();
  const error = new ConnectionError(
    "schema",
    "state",
    4,
    200,
    "Invalid editable terms",
  );
  expect(
    describeConnectionError(connectionDiagnostic(error, "state")),
  ).toContain("商品名・条件");
  const unknown = connectionDiagnostic(new Error("private exception"), "state");
  expect(unknown.code).toBe("unknown");
  expect(JSON.stringify(unknown)).not.toContain("private");
});
