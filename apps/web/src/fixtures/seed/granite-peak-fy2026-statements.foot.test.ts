// F-08-T27 (DEC-6025): the TPL-22 footings as tests (F-08 G1). Row acceptance: "Seed tests foot
// the balance sheets to 26,410,000 and the lineage 11,906,000 - 486,000 = 11,420,000, and Note 9
// reads through October 27, 2026."
import { describe, expect, it } from "vitest";
import type { LineItemDraft } from "../contracts/statements";
import { BALANCE_SHEET, STATEMENTS } from "./granite-peak-fy2026-statements";

type Year = "2026" | "2025";
const byKey = new Map(BALANCE_SHEET.map((l) => [l.key, l]));
const line = (key: string): LineItemDraft => {
  const found = byKey.get(key);
  if (found === undefined) throw new Error(`no line ${key}`);
  return found;
};
/** A formula line's value from its terms, recursively; an override overrides `ltd`. */
function value(key: string, year: Year, ltd?: number): number {
  const l = line(key);
  if (key === "ltd" && ltd !== undefined) return ltd;
  if (l.source !== "formula") return l.amounts[year];
  return (l.formula ?? []).reduce(
    (n, term) =>
      term.startsWith("-") ? n - value(term.slice(1), year, ltd) : n + value(term, year, ltd),
    0,
  );
}

describe("F-08-T27 Granite Peak FY2026 statements (TPL-22)", () => {
  it("acceptance: the balance sheets foot both years to 26,410,000 and 23,200,000", () => {
    for (const year of ["2026", "2025"] as const) {
      for (const l of BALANCE_SHEET.filter((x) => x.source === "formula")) {
        expect(value(l.key, year), `${l.key} ${year}`).toBe(l.amounts[year]);
      }
      expect(value("total_assets", year)).toBe(value("total_liabilities_equity", year));
    }
    expect(value("total_assets", "2026")).toBe(26410000);
    expect(value("total_assets", "2025")).toBe(23200000);
    expect(value("current_assets", "2026")).toBe(19420000);
    expect(value("total_liabilities", "2026")).toBe(15510000);
    expect([
      value("current_assets", "2025"),
      value("current_liabilities", "2025"),
      value("total_liabilities", "2025"),
    ]).toEqual([16510000, 5450000, 13550000]);
  });

  it("acceptance: the lineage foots 11,906,000 − 486,000 = 11,420,000", () => {
    const inventory = line("inventory");
    const groups = inventory.groups ?? [];
    expect(groups.map((g) => g.account)).toEqual(["1300 Inventory", "1450 Inventory reserve"]);
    expect(groups.reduce((n, g) => n + g.amount, 0)).toBe(11420000);
    expect(inventory.amounts["2026"]).toBe(11420000);
  });

  it("the cash-flow change agrees: 11,420,000 − 9,180,000 = 2,240,000", () => {
    const inventory = line("inventory").amounts;
    const change = STATEMENTS.usedIn.find((u) => u.label.startsWith("Statements of cash flows"));
    expect(-(inventory["2026"] - inventory["2025"])).toBe(change?.amount);
  });

  it("the 9:40 stale override puts the totals at 16,110,000 / 27,010,000; the relink restores them", () => {
    const [relink] = STATEMENTS.relinks;
    expect([relink?.from, relink?.to, relink?.at]).toEqual([3200000, 2600000, "2026-10-21T10:24"]);
    expect(value("total_liabilities", "2026", relink?.from)).toBe(16110000);
    expect(value("total_liabilities_equity", "2026", relink?.from)).toBe(27010000);
    expect(
      value("total_liabilities_equity", "2026", relink?.from) - value("total_assets", "2026"),
    ).toBe(600000);
    expect(value("total_liabilities_equity", "2026", relink?.to)).toBe(26410000);
  });

  it("tie-out reads 214 of 214 only after run #2 at 10:26", () => {
    const [first, second] = STATEMENTS.tieOuts;
    expect([first?.at, first?.differences, first?.staleOverrides]).toEqual([
      "2026-10-21T09:13",
      1,
      1,
    ]);
    expect([second?.at, (second?.total ?? 0) - (second?.differences ?? 1)]).toEqual([
      "2026-10-21T10:26",
      214,
    ]);
    expect(STATEMENTS.rollForward.map((s) => s.done.slice(11))).toEqual([
      "09:06",
      "09:09",
      "09:11",
      "09:12",
    ]);
  });

  it("acceptance: Note 9 reads through October 27, 2026, on page 13 of 13", () => {
    expect(STATEMENTS.note9.kept).toContain("through October 27, 2026");
    expect(STATEMENTS.note9.page).toBe(STATEMENTS.pageCount);
    expect(STATEMENTS.pageCount).toBe(13);
    expect(STATEMENTS.note9.attribution).toBe("HL via Agent");
    expect(STATEMENTS.note9.sources).toHaveLength(3);
  });

  it("presence: Hannah editing, Simone viewing Note 5; Margaret viewed at 10:40", () => {
    expect(STATEMENTS.presence.map((p) => [p.initials, p.doing, p.where])).toEqual([
      ["HL", "editing", "Balance sheets"],
      ["SB", "viewing", "Note 5"],
    ]);
    expect(STATEMENTS.previouslyViewed).toEqual([
      { person: "Margaret Okonkwo", at: "2026-10-21T10:40" },
    ]);
  });

  it("only the first line and the double-ruled totals carry $", () => {
    const dollars = BALANCE_SHEET.filter((l) => l.dollar).map((l) => l.key);
    expect(dollars).toEqual(["cash", "total_assets", "payables", "total_liabilities_equity"]);
  });
});
