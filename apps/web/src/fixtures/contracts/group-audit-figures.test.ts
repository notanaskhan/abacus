// A-09-T06 (SPEC-658 AC-0.3, AC-0.5, AC-0.6): the group-audit typed fixtures foot, and fail when a
// seed total stops footing. 187,860,000 interim debits; 244 = 32 + 8 + 98 + 76 + 30; total assets
// 50,760,000 after (48,640,000) of eliminations; 67,840,000 Dr = Cr; Level 2 39,760,000;
// 240,000 / 180,000 / 12,000; component PMs 384,000; POR-23 a in client words only.
import { describe, expect, it } from "vitest";
import {
  ACCOUNTS_BY_ENTITY,
  COMPONENT_ROOM_INVITED,
  CONSOLIDATED_TB_L1,
  CONSOLIDATED_TB_L2,
  CONSOLIDATION_REVIEW,
  ELIMINATIONS,
  ENTITY_KEYS,
  GROUP_SCOPING_DECIDED,
  interimDebits,
  sumSection,
} from "../seed/group-audit";

describe("A-09 group-audit fixtures", () => {
  it("AUD-32 d: interim debits foot 187,860,000", () => {
    expect(ENTITY_KEYS.map(interimDebits)).toEqual([
      30_760_000, 20_000_000, 86_000_000, 42_400_000, 8_700_000,
    ]);
    expect(CONSOLIDATION_REVIEW.interim_total_debits).toBe("187860000.00");
    expect(CONSOLIDATION_REVIEW.tiers).toBe(3);
    expect(CONSOLIDATION_REVIEW.entities.every((e) => e.ownership_pct === "100.000000")).toBe(
      true,
    );
  });

  it("AUD-31: 244 accounts across five entities", () => {
    expect(Object.values(ACCOUNTS_BY_ENTITY).reduce((a, b) => a + b, 0)).toBe(244);
  });

  it("AUD-33 a: every column nets to zero; total assets 50,760,000; NI 3,500,000", () => {
    for (const column of CONSOLIDATED_TB_L1.columns) {
      const net = CONSOLIDATED_TB_L1.rows.reduce(
        (a, r) => a + Number(r.cells.find((c) => c.column === column)?.amount ?? 0),
        0,
      );
      expect(net).toBe(0);
    }
    expect(CONSOLIDATED_TB_L1.tallies.total_assets).toBe("50760000.00");
    expect(sumSection(CONSOLIDATED_TB_L1.rows, "assets", "eliminations")).toBe(-48_640_000);
    expect(CONSOLIDATED_TB_L1.tallies.net_income).toBe("3500000.00");
  });

  it("AUD-33: eliminations total 67,840,000 Dr = Cr and each balances", () => {
    expect(ELIMINATIONS.total_debit).toBe("67840000.00");
    expect(ELIMINATIONS.total_credit).toBe("67840000.00");
    expect(ELIMINATIONS.items.map((e) => e.display_code)).toEqual([
      "E1a",
      "E1b",
      "E2",
      "E3",
      "E4",
      "E5",
    ]);
    for (const e of ELIMINATIONS.items) {
      expect(e.off_by).toBe("0.00");
      expect(e.posting_target).toBe("consolidation_layer");
    }
  });

  it("AUD-33 d: Level 2 · Operating Co. reads 39,760,000 and NI 4,760,000", () => {
    expect(CONSOLIDATED_TB_L2.tallies.total_assets).toBe("39760000.00");
    expect(CONSOLIDATED_TB_L2.tallies.net_income).toBe("4760000.00");
    expect(sumSection(CONSOLIDATED_TB_L2.rows, "assets", "eliminations")).toBe(-22_640_000);
  });

  it("AUD-34 c: 240,000 · 180,000 · 12,000; component PMs below group PM sum 384,000", () => {
    expect(GROUP_SCOPING_DECIDED.group_materiality).toBe("240000.00");
    expect(GROUP_SCOPING_DECIDED.performance_materiality).toBe("180000.00");
    expect(GROUP_SCOPING_DECIDED.clearly_trivial).toBe("12000.00");
    const pms = GROUP_SCOPING_DECIDED.components.map((c) => Number(c.component_pm ?? 0));
    expect(pms.reduce((a, b) => a + b, 0)).toBe(384_000);
    expect(pms.every((pm) => pm < 180_000)).toBe(true);
    expect(GROUP_SCOPING_DECIDED.components.map((c) => c.pm_pct_of_group)).toEqual([
      "75",
      "58",
      "30",
      "50",
    ]);
  });

  it("AUD-34 e: total assets 78% full scope and 22% specific procedures of 50,760,000", () => {
    const assets = GROUP_SCOPING_DECIDED.coverage.find((c) => c.measure === "total_assets");
    if (assets === undefined) throw new Error("no total-assets coverage");
    expect(Number(assets.full_scope) + Number(assets.specific_procedures)).toBe(
      Number(assets.total),
    );
    expect(Math.round((Number(assets.full_scope) * 100) / Number(assets.total))).toBe(78);
  });

  it("POR-23 a: one component, client words only, 0 of 4", () => {
    expect(COMPONENT_ROOM_INVITED.component_name).toBe("Harlow & Pike Distribution, Inc.");
    expect(
      `${String(COMPONENT_ROOM_INVITED.uploaded)} of ${String(COMPONENT_ROOM_INVITED.expected)}`,
    ).toBe("0 of 4");
    const text = JSON.stringify(COMPONENT_ROOM_INVITED);
    for (const firmOnly of [
      "Expected",
      "Reviewed",
      "Late",
      "Accrued",
      "materiality",
      "Holdings 32",
    ]) {
      expect(text.includes(firmOnly)).toBe(false);
    }
  });
});
