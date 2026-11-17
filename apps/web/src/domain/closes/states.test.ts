// C-01-T42: a closes read's C-20 state (403 role, 404 walled, else error with Retry) and when a
// close run is live (polled every 2 s without SSE).
import { describe, expect, it, vi } from "vitest";
import { RUN_POLL_MS, closeReadState, runIsLive } from "./states";

const read = (error: unknown, pending = false) => ({
  isPending: pending,
  isError: error !== null,
  error,
  refetch: vi.fn(),
});

describe("closeReadState", () => {
  it("a 403 is the role's restricted notice and a 404 never reveals the close", () => {
    expect(closeReadState(read({ status: 403 }))).toEqual({ kind: "restricted", reason: "role" });
    expect(closeReadState(read({ detail: "not_found" }))).toEqual({
      kind: "restricted",
      reason: "walled",
    });
  });

  it("any other failure is the error with Retry, which refetches", () => {
    const r = read({ status: 500 });
    const state = closeReadState(r);
    expect(state.kind).toBe("error");
    if (state.kind === "error") state.retry();
    expect(r.refetch).toHaveBeenCalledOnce();
  });

  it("loading, then ready", () => {
    expect(closeReadState(read(null, true))).toEqual({ kind: "loading" });
    expect(closeReadState(read(null))).toEqual({ kind: "ready" });
  });
});

describe("runIsLive", () => {
  it("polls a running or waiting run every 2 s and stops after", () => {
    expect(RUN_POLL_MS).toBe(2_000);
    expect(runIsLive("running")).toBe(true);
    expect(runIsLive("needs_input")).toBe(true);
    expect(runIsLive("complete")).toBe(false);
    expect(runIsLive(undefined)).toBe(false);
  });
});
