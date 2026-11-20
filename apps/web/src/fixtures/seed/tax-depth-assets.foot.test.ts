// T-06-T29: the fixture register foots the way the T-06-T22 slice does (T-06 §3 F1): cost
// 15,752,000; 1,891,667 + 733,500 = 2,625,167; 733,500 by property 169,500 + 360,000 + 204,000.
import { describe, expect, it } from "vitest";
import { PROPERTIES, fixedAssets, rowsOf } from "./tax-depth-assets";

const sum = (xs: readonly string[]): bigint => xs.reduce((s, x) => s + BigInt(x), 0n);

describe("TXP-03 fixture register foots", () => {
  const rows = rowsOf("e0");
  const fa = fixedAssets("register", "e0");
  it("cost, prior, current and accumulated", () => {
    expect(sum(rows.map((r) => r.cost))).toBe(BigInt(fa.depreciable_cost));
    expect(sum(rows.map((r) => r.prior))).toBe(1891667n);
    expect(sum(rows.map((r) => r.current))).toBe(BigInt(fa.current));
    expect(1891667n + BigInt(fa.current)).toBe(BigInt(fa.accumulated));
    for (const r of rows) expect(BigInt(r.prior) + BigInt(r.current)).toBe(BigInt(r.accumulated));
  });
  it("by property and land", () => {
    expect(sum(PROPERTIES.map((p) => p.depreciation))).toBe(BigInt(fa.current));
    expect(sum(PROPERTIES.map((p) => p.land))).toBe(BigInt(fa.land));
    for (const p of PROPERTIES) {
      const own = rows.filter((r) => r.property_key === p.property_key).map((r) => r.current);
      expect(sum(own)).toBe(BigInt(p.depreciation));
    }
  });
  it("the Larimer bonus is Check until the Feb 3, 2025 contract matches", () => {
    const parking = (v: "e0" | "bonusResolved") =>
      rowsOf(v).find((r) => r.description === "Larimer parking lot resurfacing")?.bonus_check;
    expect(parking("e0")).toBe("check");
    expect(parking("bonusResolved")).toBe("tie");
  });
});
