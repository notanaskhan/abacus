// T-06-T31: the fixture basis foots (T-06 §3 F3): inside 17,914,500 against outside 17,943,095, four
// of five reconcile, Pell Street II off by the 28,595 placeholder, and the §752 parts sum to
// 10,712,500 + 335,800.
import { describe, expect, it } from "vitest";
import { BASIS_PARTNERS, PELL_II_ID, PELL_II_PLACEHOLDER, basis } from "./tax-depth-basis";

const sum = (xs: readonly (string | null | undefined)[]): bigint =>
  xs.reduce((s, x) => s + BigInt(x ?? "0"), 0n);

describe("TXP-08 fixture basis foots", () => {
  const b = basis("basis");
  it("inside and outside totals, and four of five reconcile", () => {
    expect(sum(BASIS_PARTNERS.map((p) => p.inside))).toBe(BigInt(b.inside_total));
    expect(sum(BASIS_PARTNERS.map((p) => p.outside))).toBe(BigInt(b.outside_total));
    expect(BASIS_PARTNERS.filter((p) => p.tally === "tie")).toHaveLength(b.reconciled);
    const ps2 = BASIS_PARTNERS.find((p) => p.partner_id === PELL_II_ID);
    expect(BigInt(ps2?.outside ?? "0") - BigInt(ps2?.inside ?? "0")).toBe(
      BigInt(PELL_II_PLACEHOLDER),
    );
    expect(360000n - 331405n).toBe(BigInt(PELL_II_PLACEHOLDER));
  });
  it("§752: QNR 10,712,500 and other nonrecourse 335,800", () => {
    expect(sum(BASIS_PARTNERS.map((p) => p.qualified_nonrecourse))).toBe(10712500n);
    expect(sum(BASIS_PARTNERS.map((p) => p.other_nonrecourse))).toBe(335800n);
  });
});
