// W-02-T04 (TASK-7602, DEC-4602): WB-01's filter labels, the season stage groups and the
// ApprovalCard words come from the status registry (C2), never from screen code.
import { describe, expect, it } from "vitest";

import { STATUS_REGISTRY } from "./status.gen";

type Code = { label: string; derived: boolean; contextLabels?: Record<string, string> };
const codes = (object: string): Record<string, Code> =>
  (STATUS_REGISTRY as unknown as Record<string, Record<string, Code>>)[object] ?? {};

describe("W-02-T04 status rows", () => {
  it("lists WB-01's five filters, derived and never stored", () => {
    const filters = codes("workbench_session_filter");
    expect(Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, v.label]))).toEqual({
      all: "All sessions",
      mine: "Mine",
      via_agent: "Via Agent",
      running: "Running {n}",
      needs_answer: "Needs your answer {n}",
    });
    expect(Object.values(filters).every((c) => c.derived)).toBe(true);
  });

  it("maps every open return status to one season stage (WB-03 d2 definition row)", () => {
    const ret = codes("return");
    const stage = (code: string) => ret[code]?.contextLabels?.season_stage;
    expect([stage("not_started"), stage("gathering")]).toEqual(["Gather", "Gather"]);
    expect([stage("preparing"), stage("prepared")]).toEqual(["Prepare", "Prepare"]);
    expect([stage("in_review"), stage("action_required")]).toEqual(["Review", "Review"]);
    expect([stage("approved"), stage("awaiting_signature")]).toEqual(["Deliver", "Deliver"]);
    expect([stage("filed"), stage("accepted")]).toEqual(["Done", "Done"]);
    expect(Object.values(ret).every((c) => c.contextLabels?.season_stage !== undefined)).toBe(
      true,
    );
  });

  it("gives the ApprovalCard its waiting and approved words", () => {
    const proposal = codes("proposal");
    expect(proposal.pending?.contextLabels).toMatchObject({
      approval_card_owner: "Waiting on you",
      approval_card_other: "Waiting on {person}",
    });
    expect(proposal.approved?.contextLabels?.approval_card).toBe(
      "✓ Approved by {person} · {time}",
    );
  });
});
