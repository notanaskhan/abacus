// I-02-T05 (TASK-7613): the Today family's consumer assertions for SHL-23 1–7 and HOME-05 a–f
// (docs/contracts/today.md). The fixtures are typed with the generated client and validated
// against the OpenAPI document; the counts foot to HOME-01's (I-COUNT). The pytest half is
// backend/tests/contracts/today/.
import { describe, expect, it } from "vitest";
import { validateResponse, validateSchema } from "../schema-check";
import {
  HISTORY,
  QUESTION_ACCEPTED,
  buildingToday,
  byEngagementToday,
  danielToday,
  margaretDec1,
  margaretToday,
  quietToday,
  ridgelineDrill,
} from "../seed/today";

const STATES = {
  "SHL-23 1 / HOME-05 a, c": danielToday,
  "SHL-23 4 / HOME-05 d": margaretToday,
  "SHL-23 5 (fixture until A-09)": margaretDec1,
  "SHL-23 6": quietToday,
  "SHL-23 7 / HOME-05 e": buildingToday,
  "HOME-05 f (by_engagement)": byEngagementToday,
};

const bandSum = (cells: { kind: string; count: number }[]) =>
  cells.filter((c) => c.kind !== "overdue").reduce((a, c) => a + c.count, 0);

describe("Today consumer (SHL-23, HOME-05)", () => {
  it.each(Object.entries(STATES))("%s validates against GET /v1/me/today", (_, make) => {
    expect(validateResponse("get", "/v1/me/today", make())).toEqual([]);
  });

  it("the drill-in, history and the accepted question validate (SHL-23 2, 3; History)", () => {
    expect(
      validateResponse("get", "/v1/me/today/work-items/{work_item_id}", ridgelineDrill()),
    ).toEqual([]);
    expect(validateResponse("get", "/v1/me/today/history", HISTORY)).toEqual([]);
    expect(validateSchema("TodayQuestionAcceptedOut", QUESTION_ACCEPTED)).toEqual([]); // 202
  });

  it("Daniel's cells equal HOME-01's 11 and Margaret's equal her 4 (I-COUNT)", () => {
    const d = danielToday();
    expect(d.cells.map((c) => [c.kind, c.count])).toEqual([
      ["decision", 3],
      ["sign_off", 6],
      ["approval_send", 2],
      ["overdue", 0],
    ]);
    expect(bandSum(d.cells)).toBe(d.items);
    const m = margaretToday();
    expect(bandSum(m.cells)).toBe(4);
    expect(m.items).toBe(4);
  });

  it("Due tomorrow 9 and Ready for sign-off 4 = 6 − Capital Accounts − Basis", () => {
    const groups = Object.fromEntries(danielToday().groups.map((g) => [g.key, g.count]));
    expect(groups).toMatchObject({ high_risk: 1, late: 0, due_tomorrow: 9, ready_for_signoff: 4 });
    const drill = ridgelineDrill();
    expect(drill.blockers).toHaveLength(2);
    expect(6 - drill.blockers.length).toBe(groups.ready_for_signoff);
  });

  it("Late is always present; quiet days hold no rows", () => {
    for (const make of Object.values(STATES)) {
      expect(make().groups.some((g) => g.key === "late")).toBe(true);
    }
    expect(quietToday().needs_you_first).toEqual([]);
  });

  it("reserved items are never prefilled and the agent is never an assignee (INV-1)", () => {
    const drill = ridgelineDrill();
    const prefills = drill.prefills ?? [];
    const reserved = new Set((drill.not_assignable ?? []).map((n) => n.gate_id));
    expect(prefills.every((p) => !reserved.has(p.gate_id))).toBe(true);
    expect(prefills.map((p) => p.assignee_name)).toEqual(["Samuel Ito"]);
  });

  it("a building brief asks for its build and shows no snapshot", () => {
    const b = buildingToday();
    expect([b.status, b.needs_build, b.brief_id]).toEqual(["building", true, null]);
  });
});
