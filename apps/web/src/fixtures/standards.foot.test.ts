// KNW-04's figures foot (K-02-T13; docs/screens/KNW-04.md "Figures"): the AJE examples, the
// checklist counts and the materiality examples, from the fixture seed.
import { describe, expect, it } from "vitest";
import { EXAMPLES, STANDARDS } from "./seed/standards";

describe("KNW-04 figures", () => {
  it("AJE: 11,860 + 700 + 2,140 + 5,320 = 20,020 within; 14,900 held (> $10,000)", () => {
    const rows = EXAMPLES["bh-aje-thresholds"]?.rows ?? [];
    const within = rows.filter((r) => r.outcome === "within_threshold");
    expect(within.reduce((t, r) => t + (r.amount_usd ?? 0), 0)).toBe(20020);
    const held = rows.filter((r) => r.outcome === "review_required");
    expect(held.map((r) => r.amount_usd)).toEqual([14900]);
  });

  it("checklists: 162 + 38 + 12 + 5 + 6 + 1 = 224 TY2025 returns; 1065 v4 has 42 checks", () => {
    const lists = STANDARDS.filter((s) => s.kind === "review_checklist");
    expect(lists.reduce((t, s) => t + (s.usage ?? 0), 0)).toBe(224);
    const f1065 = lists.find((s) => s.key === "bh-1065-review-checklist");
    expect(f1065?.version).toBe(4);
    expect(f1065?.entries).toBe(42);
  });

  it("materiality: 252,200 × 75% = 189,150 and × 5% = 12,610; 155,000 × 75% = 116,250, × 5% = 7,750", () => {
    expect((252200 * 75) / 100).toBe(189150);
    expect((252200 * 5) / 100).toBe(12610);
    expect((155000 * 75) / 100).toBe(116250);
    expect((155000 * 5) / 100).toBe(7750);
    const rows = EXAMPLES["bh-materiality-ranges"]?.rows ?? [];
    expect(rows.map((r) => r.cells?.performance)).toEqual(["75% · $189,150", "75% · $116,250"]);
  });
});
