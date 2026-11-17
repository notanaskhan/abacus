import type { RunRowOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { isDataBoundaryClosed, rowState, toRunRows } from "./runs";

function row(over: Partial<RunRowOut>): RunRowOut {
  return {
    kind: "flux_explain",
    label: "Figure out why these lines changed from last year and trace it back to the source",
    run_ids: [],
    items: 2,
    states: [],
    attribution: "Simone Baptiste via Agent",
    tb_balanced: null,
    started_at: "2026-09-13T22:36:00Z",
    ...over,
  };
}

describe("fieldwork run rows (A-08-T24)", () => {
  it("reads a code row as done and an agent row by its runs", () => {
    expect(rowState(row({ kind: "tie_out", attribution: "Code" }))).toBe("done");
    expect(rowState(row({ states: [{ state: "running", runs: 1 }] }))).toBe("running");
    expect(rowState(row({ states: [{ state: "completed", runs: 2 }] }))).toBe("done");
    expect(rowState(row({ states: [{ state: "failed", runs: 1 }] }))).toBe("failed");
  });

  it("keeps the attribution verbatim", () => {
    const [shown] = toRunRows([row({})]);
    expect(shown?.meta).toBe("Simone Baptiste via Agent");
  });

  it("recognises DF-04", () => {
    expect(isDataBoundaryClosed({ detail: "drafting_not_enabled" })).toBe(true);
    expect(isDataBoundaryClosed({ detail: { code: "drafting_not_enabled" } })).toBe(true);
    expect(isDataBoundaryClosed({ detail: "content_changed" })).toBe(false);
    expect(isDataBoundaryClosed(null)).toBe(false);
  });
});
