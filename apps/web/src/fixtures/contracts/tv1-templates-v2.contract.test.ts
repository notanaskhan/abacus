// K-03-T10 (TASK-8854; C22): the TV-1 fixture half. Every KNW-06, KNW-07, SHL-22 and SHT-03
// artboard has a scenario, and the figures the boards read foot: Added 3 · Changed 5 · Removed 0.
import { describe, expect, it } from "vitest";
import { scenarios as knw06 } from "../scenarios/KNW-06";
import { scenarios as knw07 } from "../scenarios/KNW-07";
import { scenarios as shl22 } from "../scenarios/SHL-22";
import { scenarios as sht03 } from "../scenarios/SHT-03";
import { CHANGES, CHECKS_FAILING, rollout, scopingPreview, update } from "../seed/templates-v2";

describe("TV-1 consumer (fixtures)", () => {
  it("serves all 24 artboards", () => {
    expect(Object.keys(knw06)).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(Object.keys(knw07)).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    expect(Object.keys(shl22)).toEqual(["a", "b", "c", "d", "e"]);
    expect(Object.keys(sht03)).toEqual(["a", "b", "c", "d", "e", "f"]);
  });
  it("Added 3 · Changed 5 · Removed 0", () => {
    expect([CHANGES.added, CHANGES.changed, CHANGES.removed]).toEqual([3, 5, 0]);
    expect(update("applying", 5).applied).toBe(5);
  });
  it("KNW-06c: 2 errors · 1 warning; KNW-07a: 6 live · 3 Update now · 3 Hold", () => {
    expect([CHECKS_FAILING.errors, CHECKS_FAILING.warnings]).toEqual([2, 1]);
    const r = rollout();
    expect([r.live, r.update_now, r.on_rollover, r.hold]).toEqual([6, 3, 0, 3]);
  });
  it("SHT-03a: Shows 3 steps · 2 sheets · hides 1 · adds 6 requests", () => {
    const p = scopingPreview("harlow");
    expect([p.shows_steps, p.shows_sheets, p.hides, p.adds_requests]).toEqual([3, 2, 1, 6]);
  });
});
