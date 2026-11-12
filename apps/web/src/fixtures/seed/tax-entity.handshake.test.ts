// T-05-T24 (TASK-7408; T-05 §8 handshake step 1; DEC-4407): the fixture's trial balance and run
// read as the three providers will serve them, so the screens built on fixtures need no change when
// C8's tax layers (T-05-T25), C9's form-line taxonomy (T-05-T26) and the workbook run's steps
// (T-05-T32) land. The backend half is `backend/tests/contracts/t05_consumers/`.
import { describe, expect, it } from "vitest";
import { TASKS, trialBalance } from "./tax-entity";

/** Whole-dollar decimal strings to integers (test arithmetic only; the browser never sums). */
function n(v: string | number | null | undefined): number {
  return Number(v ?? 0);
}

// The published Form 1065 line keys the mapper suite freezes (evals/tax_account_mapper).
const KEY = /^(L\d+[ab]?|K \d+[a-z]?|8825 .+|M-2 \d[a-z]?|M-3 perm\.)$/;

describe("C8: the trial balance's tax layers", () => {
  const rows = trialBalance("run2").rows;

  it("states every row's tax basis as UTB + AJE + RJE + TJE", () => {
    for (const r of rows) {
      expect(n(r.tax_basis), r.account_code).toBe(
        n(r.unadjusted) + n(r.aje) + n(r.rje) + n(r.tje),
      );
    }
  });

  it("nets the TJE layer to zero (a reclass, TJE-1)", () => {
    expect(rows.reduce((sum, r) => sum + n(r.tje), 0)).toBe(0);
    expect(rows.some((r) => n(r.tje) !== 0)).toBe(true);
  });

  it("carries 4510-T in the tax layer only (account_scope tax_only)", () => {
    const taxOnly = rows.find((r) => r.account_code === "4510-T");
    expect(taxOnly).toBeDefined();
    expect(n(taxOnly?.unadjusted)).toBe(0);
    expect(n(taxOnly?.aje) + n(taxOnly?.rje)).toBe(0);
    expect(n(taxOnly?.tje)).not.toBe(0);
  });
});

describe("C9: the form-line taxonomy", () => {
  it("maps every Run 2 account to a published key", () => {
    const run2 = trialBalance("run2");
    expect(run2.unmapped).toBe(0);
    for (const r of run2.rows) {
      expect(r.form_line_key ?? "", r.account_code).toMatch(KEY);
    }
  });

  it("leaves Run 1's account 1300 unmapped and counts it", () => {
    const run1 = trialBalance("run1");
    expect(run1.unmapped).toBe(1);
    expect(run1.rows.filter((r) => r.form_line_key === null).map((r) => r.account_code)).toEqual([
      "1300",
    ]);
  });
});

describe("C6 v2: the workbook run's plan", () => {
  it("has the design's ten tasks in order", () => {
    expect(TASKS).toHaveLength(10);
    expect(TASKS[0]).toBe("Import trial balance");
    expect(TASKS[1]).toBe("Map to Form 1065 lines");
    expect(TASKS[6]).toBe("Capital accounts & Schedule M-2");
    expect(TASKS[8]).toBe("Federal K-1s (5)");
  });
});
