// ENG-05's figures on the seed (P-07-T39; docs/screens/ENG-05.md, Figures): Northwind's budget
// hours foot to 172.0 (10 + 6 + 37 + 61 + 40 + 18) and ENG-06's actuals to 24.0 (1 + 0 + 7 + 12 +
// 4; Kira Ross has none), the same figures as ENG-06; the confirmed team is AUD-02's rail
// "Team: MO · TW · HL · MD · AC" and the pending Kira Ross is not on it.
import { describe, expect, it } from "vitest";
import { hoursText, hoursTotal } from "../domain/engagements";
import { personInitials } from "@abacus/ui";
import { NORTHWIND_TEAM, actualsOf, rosterOf } from "./seed/team-roles";

describe("ENG-05 figures", () => {
  it("Northwind's budget hours foot to 172.0 and actuals to 24.0", () => {
    const roster = rosterOf(NORTHWIND_TEAM);
    const budget = hoursTotal(roster.map((m) => m.budget_hours));
    const actual = hoursTotal(actualsOf(NORTHWIND_TEAM));
    expect(budget === null ? null : hoursText(budget)).toBe("172.0");
    expect(actual === null ? null : hoursText(actual)).toBe("24.0");
  });

  it("the confirmed team is AUD-02's rail, MO · TW · HL · MD · AC, without Kira Ross", () => {
    const confirmed = rosterOf(NORTHWIND_TEAM).filter((m) => m.independence === "confirmed");
    expect(confirmed.map((m) => personInitials(m.display_name)).join(" · ")).toBe(
      "MO · TW · HL · MD · AC",
    );
    expect(confirmed.some((m) => m.display_name === "Kira Ross")).toBe(false);
  });
});
