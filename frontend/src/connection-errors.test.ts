import { afterEach, expect, it, vi } from "vitest";
import { readSearch, sendSearch } from "./connected-api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it.each([
  [
    "network",
    () => Promise.reject(new TypeError("private network detail")),
    null,
  ],
  [
    "http",
    () => Promise.resolve(new Response("private response", { status: 503 })),
    503,
  ],
  ["json", () => Promise.resolve(new Response("private invalid JSON")), 200],
  [
    "schema",
    () =>
      Promise.resolve(Response.json({ stage: "private-stage", revision: 0 })),
    200,
  ],
] as const)(
  "identifies %s failures without retaining response or exception text",
  async (code, fetcher, status) => {
    vi.stubGlobal("fetch", vi.fn(fetcher));
    const error = await readSearch().catch((value: unknown) => value);
    expect(error).toMatchObject({
      diagnostic: {
        code,
        operation: "state",
        httpStatus: status,
        elapsedMs: expect.any(Number),
        occurredAt: expect.any(String),
      },
    });
    expect(JSON.stringify(error)).not.toContain("private");
  },
);

it("identifies timeouts while reading either headers or the response body", async () => {
  for (const body of [false, true]) {
    const controller = new AbortController();
    const timeout = vi
      .spyOn(AbortSignal, "timeout")
      .mockReturnValue(controller.signal);
    const fail = () => {
      controller.abort(new DOMException("private timeout", "TimeoutError"));
      return Promise.reject(controller.signal.reason);
    };
    vi.stubGlobal(
      "fetch",
      body ? async () => ({ ok: true, status: 200, json: fail }) : fail,
    );
    const error = await readSearch().catch((value: unknown) => value);
    expect(error).toMatchObject({
      diagnostic: {
        code: "timeout",
        operation: "state",
        httpStatus: body ? 200 : null,
      },
    });
    expect(JSON.stringify(error)).not.toContain("private");
    timeout.mockRestore();
  }
});

it("records command rejection without repeating the command or retaining its input", async () => {
  const fetcher = vi.fn(
    async () => new Response("private response", { status: 409 }),
  );
  vi.stubGlobal("fetch", fetcher);
  const error = await sendSearch(
    "start",
    { stage: "idle", revision: 0 },
    { source: "private input" },
  ).catch((value: unknown) => value);
  expect(error).toMatchObject({
    diagnostic: { code: "http", operation: "command", httpStatus: 409 },
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(JSON.stringify(error)).not.toContain("private");
});

it("keeps successful state responses unchanged", async () => {
  const state = { stage: "idle", revision: 0 };
  vi.stubGlobal("fetch", async () => Response.json(state));
  expect(await readSearch()).toEqual(state);
});

it("distinguishes a body transfer failure from invalid JSON", async () => {
  vi.stubGlobal("fetch", async () => ({
    ok: true,
    status: 200,
    json: () => Promise.reject(new TypeError("private transfer error")),
  }));
  const error = await readSearch().catch((value: unknown) => value);
  expect(error).toMatchObject({
    diagnostic: { code: "network", httpStatus: 200 },
  });
  expect(JSON.stringify(error)).not.toContain("private");
});

it("distinguishes interruption from a deadline", async () => {
  const controller = new AbortController();
  vi.spyOn(AbortSignal, "timeout").mockReturnValue(controller.signal);
  vi.stubGlobal("fetch", () => {
    controller.abort();
    return Promise.reject(controller.signal.reason);
  });
  expect(await readSearch().catch((value: unknown) => value)).toMatchObject({
    diagnostic: { code: "aborted" },
  });
});
