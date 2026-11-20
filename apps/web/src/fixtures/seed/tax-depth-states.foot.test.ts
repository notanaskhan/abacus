// T-06-T32: the TXP-09 seed foots (ADR-050: the browser never computes; the seed is checked here).
import { describe, expect, it } from "vitest";
import { states } from "./tax-depth-states";

const n = (v: string | null | undefined): number => Number(v ?? "0");

describe("TXP-09 seed", () => {
  it("numerators foot to the base and shares to 100.0", () => {
    const s = states();
    expect(s.states.reduce((t, r) => t + n(r.numerator), 0)).toBe(n(s.base));
    expect(s.states.reduce((t, r) => t + Number(r.apportionment_pct), 0)).toBeCloseTo(100, 5);
    expect(s.states.reduce((t, r) => t + n(r.ptet_amount), 0)).toBe(n(s.ptet_total));
  });
  it("each credit column foots to its state and Feld reads 16,025", () => {
    const s = states();
    for (const r of s.states) {
      const col = (s.credits ?? []).reduce((t, c) => t + n(c.by_state[r.state]), 0);
      expect(col).toBe(n(r.ptet_amount));
    }
    expect((s.credits ?? []).find((c) => c.name === "Jonah Feld")?.total).toBe("16025");
  });
});
