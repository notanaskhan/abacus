// T-06-T30: the fixture book-tax schedules foot (T-06 §3 F2): (a) + (b) + (c) = (d) on every M-3
// row, the items sum to the total row, and M-2 lines 1–4 = 5, 5 − 8 = 9, both variants.
import { describe, expect, it } from "vitest";
import { M1, M3, SCHEDULE_L_21, m2 } from "./tax-depth-booktax";

const n = (v: string): bigint => BigInt(v);

describe("TXP-04 fixture schedules foot", () => {
  it("M-3 rows crossfoot and the items sum to the total", () => {
    for (const r of M3.rows) {
      expect(n(r.income_per_books) + n(r.temporary) + n(r.permanent)).toBe(n(r.per_return));
    }
    const items = M3.rows.filter((r) => r.line !== "29");
    const total = M3.rows.find((r) => r.line === "29");
    expect(items.reduce((s, r) => s + n(r.per_return), 0n)).toBe(n(total?.per_return ?? "0"));
    expect(items.reduce((s, r) => s + n(r.income_per_books), 0n)).toBe(n(M3.book_income));
    expect(M3.filed && !M1.filed).toBe(true);
  });

  it("M-1 reconciles 1,256,200 to 1,250,000", () => {
    const [books, exempt, line9] = M1.rows;
    expect(n(books?.per_return ?? "") - n(exempt?.per_return ?? "")).toBe(
      n(line9?.per_return ?? ""),
    );
  });

  it("M-2 lines foot, and only the fix ties to Schedule L 6,866,200", () => {
    for (const variant of ["as_drafted", "with_fix"] as const) {
      const s = m2(variant);
      const at = (l: number): bigint =>
        n((s.lines ?? []).find((x) => x.line === l)?.amount ?? "0");
      expect(at(1) + at(2) + at(3) + at(4)).toBe(at(5));
      expect(at(5) - at(8)).toBe(at(9));
      expect(at(9)).toBe(n(s.ending));
      expect(s.tie).toBe(at(9) === n(SCHEDULE_L_21) ? "tie" : "off");
    }
    expect(m2("with_fix").ending).toBe("6866200");
    expect(m2("as_drafted").ending).toBe("6860000");
  });
});
