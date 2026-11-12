// W-02-T02 (TASK-7604): the workbench-sessions fixtures foot to the handoff and hold DEC-87's
// rules: the eight rows, a locked row with no figure, a picker without Copperleaf, the office ×
// stage matrix both ways, and the drill's 11 returns.
import { describe, expect, it } from "vitest";
import {
  actionRequiredDrill,
  artifactPreview,
  attachedContext,
  contextOptions,
  stageDefinition,
  summaryMatrix,
  wbList,
} from "./seed/workbench";

describe("W-02 workbench-sessions fixtures", () => {
  it("lists exactly the eight WB-01 rows with via Agent on rows 2 and 5 (AC-L1)", () => {
    const { items, counts } = wbList("wb01-list-e0");
    expect(items).toHaveLength(8);
    expect(items[0]!.needs_answer).toBe(true);
    expect(items[1]!.ready_for_review).toBe(true);
    expect(items.map((r) => r.owner?.via_agent)).toEqual([
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      false,
    ]);
    expect(counts).toEqual({ running: 0, needs_answer: 1 });
  });

  it("locks the Copperleaf row and gives it nothing but metadata (AC-V1)", () => {
    const locked = wbList("wb01g-locked-copperleaf").items.filter((r) => r.locked);
    expect(locked.map((r) => r.title)).toEqual(["Explain Copperleaf July→August payroll change"]);
    expect(locked[0]!.needs_answer || locked[0]!.running || locked[0]!.ready_for_review).toBe(
      false,
    );
  });

  it("reads Running 3 at 9:24 and Running 4 from 9:25 (AC-L2)", () => {
    expect(wbList("wb01c-running-three").counts?.running).toBe(3);
    expect(wbList("wb01c-running-three").items.every((r) => r.running)).toBe(true);
    expect(wbList("wb01c-running-four").counts?.running).toBe(4);
    expect(wbList("wb01f-search-k3").items).toEqual([]);
  });

  it("never lists Copperleaf in the picker and counts nothing left out (AC-C3)", () => {
    for (const tab of ["client_record", "documents", "workpapers"] as const) {
      const titles = contextOptions(tab).items.map((i) => i.title);
      expect(titles.some((t) => t.includes("Copperleaf"))).toBe(false);
      expect(Object.keys(contextOptions(tab))).toEqual(["tab", "items"]);
    }
    expect(attachedContext().items.map((i) => i.chip_label)).toEqual([
      "Northwind Robotics 401(k) Plan",
      "PBC · 12 of 24",
      "Planning workpapers",
    ]);
  });

  it("foots the office × stage matrix both ways (AC-R2)", () => {
    const m = summaryMatrix();
    expect(m.map((r) => [r.office, ...r.cells, r.total])).toEqual([
      ["Chicago", 4, 11, 12, 7, 34],
      ["Denver", 3, 8, 7, 5, 23],
      ["New York", 3, 7, 7, 5, 22],
      ["Total", 10, 26, 26, 17, 79],
    ]);
    expect(stageDefinition()).toBe(
      "Gather = Not started 2 + Gathering 8 · Prepare = Preparing 9 + Prepared 17 · Review = In review 15 + Action required 11 · Deliver = Ready 7 + Awaiting signature 10",
    );
    expect(artifactPreview().sheets).toEqual([
      "Summary",
      "Gather",
      "Prepare",
      "Review",
      "Deliver",
    ]);
  });

  it("drills Action required to its 11 returns, each linked to TAX-02 (AC-R4)", () => {
    const drill = actionRequiredDrill();
    expect(drill.total).toBe(11);
    expect(drill.rows.every((r) => r.href.startsWith("/tax-returns/"))).toBe(true);
  });
});
