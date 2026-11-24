// Q-05-T23 (TASK-8933; DEC-5935): ADM-12's footings (handoff acceptance checklist).
import { describe, expect, it } from "vitest";
import { findings, inspections } from "./adm12";

describe("ADM-12 seed", () => {
  it("tiles 2 + 1 + 3 = 6 inspections; 1 + 1 + 0 + 1 = 3 findings from inspections", () => {
    const rows = inspections();
    const by = (s: string) => rows.filter((r) => r.status === s).length;
    expect([by("planned"), by("in_progress"), by("concluded")]).toEqual([2, 1, 3]);
    expect(rows.reduce((t, r) => t + (r.findings ?? 0), 0)).toBe(3);
  });
  it("5 findings open = 3 from inspections + 2 from agent monitoring", () => {
    const open = findings().filter((f) => f.status !== "remediated");
    expect(open).toHaveLength(5);
    expect(open.filter((f) => f.source === "agent_monitoring")).toHaveLength(2);
  });
  it("every inspector is objective: never the EP / signer", () => {
    for (const r of inspections()) expect(r.inspector.user_id).not.toBe(r.signer?.user_id);
  });
});
