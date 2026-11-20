// F-08-T15: the TPL-23 seed foots (ADR-050).
import { describe, expect, it } from "vitest";
import { AGES, DUE } from "./insights-responsiveness";

describe("TPL-23 seed", () => {
  it("firm requests due foot to 4,450 and on time is 63%", () => {
    const f = DUE.firm;
    expect(f.onTime + f.late + f.pastDue).toBe(f.due);
    expect(Math.round((f.onTime / f.due) * 100)).toBe(63);
  });
  it("past due by age foots to 214", () => {
    expect(AGES.reduce((t, a) => t + a.value, 0)).toBe(DUE.firm.pastDue);
  });
  it("Granite Peak foots to 65 and 48%", () => {
    const g = DUE.granite;
    expect(g.onTime + g.late + g.pastDue).toBe(g.due);
    expect(Math.round((g.onTime / g.due) * 100)).toBe(48);
  });
});
