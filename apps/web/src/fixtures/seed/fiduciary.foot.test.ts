// T-07-T08 (SPEC-656 AC-15.6): the trusts-and-estates fixture seed foots, and the scenario keys
// cover 25 artboards and 6 composed states. Amounts are compared in cents (the test's arithmetic,
// never the screen's).
import { describe, expect, it } from "vitest";
import { TXT_SCENARIO_KEYS } from "../scenarios/TXT";
import {
  CALLOWAY_DEDUCTION,
  callowayAllocation,
  thornburyDeductions,
  thornburyInventory,
} from "./fiduciary";

const cents = (v: string | null): number => (v === null ? 0 : Math.round(Number(v) * 100));
const sum = (values: (string | null)[]): number => values.reduce((t, v) => t + cents(v), 0);

describe("trusts-and-estates fixture seed", () => {
  it("TXT-03 a: Σ DNI allocated = the deduction, boxes 60,000 / 180,000 / 144,000", () => {
    const rows = callowayAllocation();
    expect(sum(rows.map((r) => r.dni_allocated))).toBe(cents(CALLOWAY_DEDUCTION));
    expect(sum(rows.map((r) => r.box_1))).toBe(cents("60000.00"));
    expect(sum(rows.map((r) => r.box_2a))).toBe(cents("180000.00"));
    expect(sum(rows.map((r) => r.box_2b))).toBe(cents("144000.00"));
    for (const r of rows)
      expect(sum(r.payments.map((p) => p.amount))).toBe(cents(r.distributions));
  });

  it("TXT-04 a: 16,400,000 / 15,993,000 / 12,688,000; no basis for IRD or life insurance", () => {
    const assets = thornburyInventory();
    expect(sum(assets.map((a) => a.dod_value))).toBe(cents("16400000.00"));
    expect(sum(assets.map((a) => a.avd_value))).toBe(cents("15993000.00"));
    expect(sum(assets.map((a) => a.basis_to_1041))).toBe(cents("12688000.00"));
    expect(assets.filter((a) => a.basis_to_1041 === null).map((a) => a.schedule)).toEqual([
      "D",
      "I",
    ]);
  });

  it("TXT-04 b: deductions foot 900,000 and taxable estate is 15,500,000", () => {
    const total = sum(thornburyDeductions().map((d) => d.amount));
    expect(total).toBe(cents("900000.00"));
    expect(sum(thornburyInventory().map((a) => a.dod_value)) - total).toBe(cents("15500000.00"));
  });

  it("covers 25 artboards and 6 composed states, each key once", () => {
    expect(TXT_SCENARIO_KEYS.filter((s) => !s.composed)).toHaveLength(25);
    expect(TXT_SCENARIO_KEYS.filter((s) => s.composed)).toHaveLength(6);
    expect(new Set(TXT_SCENARIO_KEYS.map((s) => s.key)).size).toBe(TXT_SCENARIO_KEYS.length);
    expect(TXT_SCENARIO_KEYS.find((s) => s.key === "txt04.c1")?.persona).toBe("daniel-reyes");
  });
});
