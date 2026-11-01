// I-01-T15 (HOME-02 acceptance): the basis table foots in every column, 360,000 − 331,405 =
// 28,595, and Daniel's bands read 3 + 6 + 2 = 11 from the one count source.
import { describe, expect, it } from "vitest";
import { countsOf, gatesFor } from "./handlers/human-gates";
import { scenarios } from "./scenarios/HOME-02";
import { getSeed } from "./seed";
import { BASIS_ROWS, BASIS_TOTAL, CALC_CARD, DANIEL_BANDS } from "./seed/approvals";

const sum = (pick: (r: (typeof BASIS_ROWS)[number]) => number): number =>
  BASIS_ROWS.reduce((t, r) => t + pick(r), 0);

describe("HOME-02 figures", () => {
  it("foots the basis table in every column", () => {
    expect(sum((r) => r.taxCapital)).toBe(BASIS_TOTAL.taxCapital);
    expect(sum((r) => r.liabilityShare)).toBe(BASIS_TOTAL.liabilityShare);
    expect(sum((r) => r.outsideBasis)).toBe(BASIS_TOTAL.outsideBasis);
    expect(sum((r) => r.insideShare)).toBe(BASIS_TOTAL.insideShare);
    // Capital plus the liability share is the inside share; a transferee's outside basis also
    // carries the price paid (Pell Street II: 913,820 outside, 885,225 inside).
    for (const r of BASIS_ROWS) expect(r.taxCapital + r.liabilityShare).toBe(r.insideShare);
    expect(BASIS_TOTAL.outsideBasis - BASIS_TOTAL.insideShare).toBe(BASIS_TOTAL.difference);
  });

  it("foots the calc card: 360,000 − 331,405 = 28,595", () => {
    const c = CALC_CARD;
    expect(c.capitalParts.reduce((t, x) => t + x, 0)).toBe(c.capitalAtSale);
    expect((c.capitalAtSale * c.transferredShare[0]) / c.transferredShare[1]).toBe(
      c.capitalTransferred,
    );
    expect(c.purchasePrice - c.capitalTransferred).toBe(c.stepUp);
    const o = c.outsideParts;
    expect(o.price + o.income + o.taxExempt - o.distributions + o.liabilities).toBe(913_820);
    expect(913_820 - 885_225).toBe(c.stepUp);
  });

  it("reads Daniel's bands 3 + 6 + 2 = 11 from the one count source", () => {
    const counts = countsOf(gatesFor(getSeed(), "daniel-reyes"));
    expect(counts.bands.decisions).toBe(DANIEL_BANDS.decisions);
    expect(counts.bands.sign_offs).toBe(DANIEL_BANDS.sign_offs);
    expect(counts.bands.approvals_sends).toBe(DANIEL_BANDS.approvals_sends);
    expect(counts.total).toBe(11);
  });

  it("names every artboard and the four queue conditions at 9:31 AM (b at 9:36)", () => {
    expect(Object.keys(scenarios)).toEqual([
      ...["a", "b", "c", "d", "e", "f", "g"],
      ...["show_done", "snoozed", "reassigned", "overdue"],
    ]);
    expect(scenarios.g.persona).toBe("samuel-ito");
    // I-01-T17 (DEC-1750): b is the moment after the §754 decision, 9:36 AM; the rest 9:31 AM.
    for (const [state, s] of Object.entries(scenarios)) {
      expect(s.clock).toBe(
        state === "b" ? "2026-09-14T09:36:00-05:00" : "2026-09-14T09:31:00-05:00",
      );
    }
  });
});
