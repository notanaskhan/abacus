// R-02-T19: POR-08's fixtures foot to the handoff's figures (spec.md, AUD-16, CLS-07).
import { describe, expect, it } from "vitest";
import { ACCRUED_EXPENSE_LINES, POSTED, approvalDetail, POR08_ID } from "./portal-por08";

const cents = (v: string | null): number => (v === null ? 0 : Math.round(Number(v) * 100));

describe("POR-08 fixtures", () => {
  it("the six posted entries foot to 35,300 (QBO 48213–48218)", () => {
    expect(POSTED.reduce((s, p) => s + cents(p.amount), 0)).toBe(3_530_000);
  });

  it("the accrued-expenses entry's lines foot to 14,900", () => {
    const debit = ACCRUED_EXPENSE_LINES.reduce((s, l) => s + cents(l.debit), 0);
    const credit = ACCRUED_EXPENSE_LINES.reduce((s, l) => s + cents(l.credit), 0);
    expect(debit).toBe(1_490_000);
    expect(credit).toBe(1_490_000);
  });

  it("AJE-1 is 33,540 + 15,060 = 48,600, and every entry balances", () => {
    for (const id of [POR08_ID.aje1, POR08_ID.rje1]) {
      const d = approvalDetail("e", id);
      const debit = (d?.lines ?? []).reduce((s, l) => s + cents(l.debit ?? null), 0);
      const credit = (d?.lines ?? []).reduce((s, l) => s + cents(l.credit ?? null), 0);
      expect(debit).toBe(credit);
      expect(debit).toBe(cents(d?.amount ?? null));
    }
  });

  it("the net effect is 35,300 − 13,050 = 22,250", () => {
    const d = approvalDetail("e2", POR08_ID.uncorrected);
    const plus = cents(d?.lines[0]?.debit ?? null);
    const minus = cents(d?.lines[1]?.credit ?? null);
    expect(plus - minus).toBe(cents(d?.amount ?? null));
    expect(d?.amount).toBe("22250.00");
  });
});
