// T-01-T09 (SPEC-501 AC-17): T-01's fixture figures foot, as the handoff's specs state them.
import { describe, expect, it } from "vitest";
import { adm05, adm08, cli05, tax09, tax12 } from "./scenarios/tax-compliance";
import {
  AI_USE_ENGAGEMENTS,
  CONSENT_SUMMARY,
  FELD_ESTIMATE,
  FELD_NY,
  FELD_PAYMENTS,
  FELD_REFUND,
  FELD_STATE_INCOME,
  FELD_STATE_TOTAL,
  RIDGELINE_PTET,
  WHITLEY_DIFFERENCES,
  WHITLEY_DUE_CENTS,
  WHITLEY_INTEREST_CENTS,
  WHITLEY_TAX_CENTS,
  WHITLEY_TOTAL_CENTS,
} from "./seed/tax-compliance";

describe("T-01 fixture figures", () => {
  it("ADM-05: 212 + 2 + 1 + 1 + 1 + 1 = 218 consents; AI-use 211 + 3 = 214", () => {
    const s = CONSENT_SUMMARY;
    expect(s.signed + s.expiring + s.requested + s.expired + s.declined + s.revoked).toBe(218);
    expect(s.total).toBe(218);
    const ai = AI_USE_ENGAGEMENTS;
    expect(ai.signed + ai.ferris + ai.stein + ai.thornbury).toBe(214);
  });

  it("TAX-09: 1.10 × 123,223 = 135,545; − 55,585 = 79,960; ÷ 4 = 19,990", () => {
    const f = FELD_ESTIMATE;
    const safe = Math.round((f.tax2025 * f.safeHarbourPct) / 100);
    expect(safe).toBe(135_545);
    expect(safe - f.withholding).toBe(79_960);
    expect((safe - f.withholding) / f.quarters).toBe(f.quarterly);
  });

  it("TAX-09: 141,634 + 96,989 + 69,277 = 307,900", () => {
    expect(FELD_STATE_INCOME.reduce((t, r) => t + r.amount, 0)).toBe(FELD_STATE_TOTAL);
  });

  it("TAX-12: refund 253, NY 1,269 due, NY estimate 7,824", () => {
    expect(FELD_REFUND.paid - FELD_REFUND.tax).toBe(253);
    expect(FELD_NY.tax - FELD_NY.withheld).toBe(1_269);
    const nySafe = Math.round((FELD_NY.tax * 110) / 100);
    expect(nySafe).toBe(58_086);
    expect((nySafe - FELD_NY.withholdingCredits) / 4).toBe(7_824);
    expect(FELD_PAYMENTS.map((p) => p.amount)).toEqual(["253", "1269", "19990", "7824"]);
  });

  it("CLI-05: 1,870.00 + 1,250.00 = 3,120.00; 22% = 686.40; + 66.61 = 753.01", () => {
    expect(WHITLEY_DIFFERENCES.reduce((t, d) => t + d.cents, 0)).toBe(WHITLEY_TOTAL_CENTS);
    expect((WHITLEY_TOTAL_CENTS * 22) / 100).toBe(WHITLEY_TAX_CENTS);
    expect(WHITLEY_TAX_CENTS + WHITLEY_INTEREST_CENTS).toBe(WHITLEY_DUE_CENTS);
  });

  it("CLI-05 e: Ridgeline's PTET 28,044, 17,070 and 18,982", () => {
    expect(RIDGELINE_PTET).toEqual([28_044, 17_070, 18_982]);
  });

  it("names every artboard of the five screens with its persona and clock", () => {
    expect(Object.keys(cli05)).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    expect(Object.keys(adm05)).toEqual(["a", "b", "c", "d", "e", "f", "g", "h"]);
    expect(Object.keys(adm08)).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    expect(Object.keys(tax09)).toEqual(["a", "a2", "b", "c", "d", "d2", "e"]);
    expect(Object.keys(tax12)).toEqual(["a", "a2", "b", "c", "c2", "d", "e"]);
    expect(adm05.e.persona).toBe("harold-stein");
    expect(tax12.c2.persona).toBe("daniel-reyes");
  });
});
