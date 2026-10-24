// P-03-T07: every figure the SHL-07 and SHL-08 fixtures draw foots (bigint cents, never floats),
// and the figures are the seed's (blueprint 01 §9.4; SHL-08 spec "Frame A figures tie to 01 §9.4").
import { parseDecimal } from "@abacus/ui";
import { SPECIMEN_SEED } from "@abacus/ui/specimens";
import { describe, expect, it } from "vitest";
import {
  HARBORLINE_ROWS,
  K1_FIGURES,
  K1_STACK,
  NORTHWIND_TB_TIE,
  TOTAL_INVESTMENTS_CITATION,
  W2_WAGES,
} from "./seed/trust";

const cents = (v: string): bigint => {
  const { units, scale } = parseDecimal(v.replace(/,/g, ""));
  return scale >= 2 ? units / 10n ** BigInt(scale - 2) : units * 10n ** BigInt(2 - scale);
};
const value = (name: string): string => HARBORLINE_ROWS.find(([n]) => n === name)?.[1] ?? "";

describe("SHL-08b and h: the Harborline statement foots", () => {
  it("six funds = 14,895,000.00; + BrokerWindow 1,605,000.00 = 16,500,000.00", () => {
    const funds = HARBORLINE_ROWS.slice(0, 6).reduce((sum, [, v]) => sum + cents(v), 0n);
    expect(funds).toBe(cents(value("Subtotal mutual funds & CITs")));
    expect(funds).toBe(cents("14,895,000.00"));
    expect(funds + cents(value("BrokerWindow SDBA"))).toBe(cents(value("TOTAL INVESTMENTS")));
    expect(TOTAL_INVESTMENTS_CITATION.value_text).toBe("16,500,000.00");
  });

  it("the trial balance ties: 16,500,000.00 + 312,400.00 = 16,812,400.00", () => {
    expect(
      cents(NORTHWIND_TB_TIE.totalInvestments) + cents(NORTHWIND_TB_TIE.notesReceivable),
    ).toBe(cents(NORTHWIND_TB_TIE.netAssetsUnadjusted));
  });

  it("the fund rows are the Northwind trial balance's, to the cent", () => {
    for (const [account, name, debit] of SPECIMEN_SEED.NORTHWIND_TB.slice(0, 7)) {
      const shown = name.startsWith("Self-directed") ? value("BrokerWindow SDBA") : value(name);
      expect(cents(shown), account).toBe(cents(debit));
    }
  });
});

describe("SHL-08a and f: the Feld K-1 figures", () => {
  it("307,900 · 4,600 · 1,550, and 6,200 × 25% = 1,550", () => {
    expect(K1_FIGURES.map((c) => c.value_text)).toEqual(["307,900", "4,600", "1,550"]);
    const tb = cents(K1_STACK[2]?.value_text ?? "");
    expect((tb * 25n) / 100n).toBe(cents("1,550"));
    expect(K1_STACK.slice(0, 2).map((c) => c.value_text)).toEqual(["1,550", "1,550"]);
  });

  it("SHL-08c: Claire's W-2 box 1 is 268,400.00", () => {
    expect(cents(W2_WAGES.value_text ?? "")).toBe(cents("268,400.00"));
  });
});
