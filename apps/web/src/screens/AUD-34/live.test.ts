// AUD-34 live (A-09-T38): the group scoping read maps to the screen's figures with no browser
// arithmetic: every number is the server's, formatted only.
import type { GroupScopingOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { liveData } from ".";

const decided: GroupScopingOut = {
  allowed_actions: [],
  clearly_trivial: "12000.00",
  component_pm_total: "384000.00",
  components: [
    {
      id: "c1",
      entity_name: "Harlow & Pike Manufacturing, LLC",
      component_pm: "135000.00",
      performed_by: "group_team",
      planned_work: "full_scope",
      pm_pct_of_group: "75",
      scope_areas: [],
      suggestion_id: null,
    },
    {
      id: "c2",
      entity_name: "Harlow & Pike Distribution, Inc.",
      component_pm: "105000.00",
      performed_by: "component_auditor",
      planned_work: "full_scope",
      pm_pct_of_group: "58.3",
      scope_areas: [],
      suggestion_id: null,
    },
  ],
  coverage: [
    {
      measure: "third_party_sales",
      total: "73000000",
      full_scope: "73000000",
      full_scope_pct: "100",
      specific_procedures: "0",
      specific_procedures_pct: "0",
    },
    {
      measure: "total_assets",
      total: "50760000",
      full_scope: "39600000",
      full_scope_pct: "78",
      specific_procedures: "11160000",
      specific_procedures_pct: "22",
    },
  ],
  decided: true,
  decided_at: "2026-09-14T20:40:00Z",
  decided_by_name: "Margaret Okonkwo",
  decision_card_id: null,
  group_materiality: "240000.00",
  options: [],
  performance_materiality: "180000.00",
};

describe("AUD-34 live figures", () => {
  it("formats the server's 240,000 · 180,000 · 12,000 and coverage 100% / 78% / 22%", () => {
    const data = liveData(decided);
    expect([data.materiality, data.pm, data.ct]).toEqual(["240,000", "180,000", "12,000"]);
    expect([data.salesFull, data.assetsFull, data.specific]).toEqual(["100%", "78%", "22%"]);
    expect(data.auditors).toBe("1");
    expect(data.rows.map((r) => r.pm)).toEqual(["135,000", "105,000"]);
  });
});
