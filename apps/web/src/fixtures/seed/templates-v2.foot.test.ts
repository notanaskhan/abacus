// K-03-T08: the TV-1 slice foots (ADR-050): Added 3 + Changed 5 + Removed 0 = 8; 3 + 0 + 3 = 6 live.
import { describe, expect, it } from "vitest";
import {
  CHANGES,
  ENGAGEMENT_TEMPLATE_CARDS,
  FS_V6_RULE_ROWS,
  FS_V6_STEPS_BY_PHASE,
  KNW01_COUNTS_V6,
  SKILL_BH_SK_430_V2,
  rollout,
  scopingRules,
  version,
} from "./templates-v2";

describe("TV-1 seed", () => {
  it("the change list foots to 8 rows", () => {
    expect(CHANGES.added + CHANGES.changed + CHANGES.removed).toBe(CHANGES.items.length);
    expect(CHANGES.items).toHaveLength(8);
  });
  it("rollout actions foot to the live count", () => {
    const r = rollout();
    expect(r.update_now + r.on_rollover + r.hold).toBe(r.live);
  });
  it("FS v6 adds 3 steps and 2 sheets over FS v5", () => {
    expect(
      version("v6", "draft").rail.program_steps - version("v5", "published").rail.program_steps,
    ).toBe(3);
    expect(version("v6", "draft").rail.sheets - version("v5", "published").rail.sheets).toBe(2);
  });

  // K-03-T15 (TASK-8931; DEC-5933): the remaining TV-1 artboards' figures.
  it("38 = 8 + 16 + 3 + 7 + 4 steps, and 41 + 6 requests by rule", () => {
    const steps = FS_V6_STEPS_BY_PHASE.map((p) => p.steps);
    expect(steps).toEqual([8, 16, 3, 7, 4]);
    expect(steps.reduce((t, n) => t + n, 0)).toBe(version("v6", "draft").rail.program_steps);
    const rail = version("v6", "draft").rail;
    expect([rail.requests, rail.requests_by_rule]).toEqual([41, 6]);
  });
  it("3 + 3 rollout rows: Update now and Hold", () => {
    const rows = rollout().rows;
    expect(rows.filter((r) => r.action === "update_now")).toHaveLength(3);
    expect(rows.filter((r) => r.action === "hold")).toHaveLength(3);
  });
  it("skill v2 at 9:34 before FS v6 at 9:38 (DF-34)", () => {
    const fs = version("v6", "published").published_at ?? "";
    expect(Date.parse(SKILL_BH_SK_430_V2.published_at)).toBeLessThan(Date.parse(fs));
    expect(fs).toBe("2026-10-01T09:38:00-05:00");
  });
  it("KNW-01 g counts foot to 107 and h lists six templates", () => {
    expect(KNW01_COUNTS_V6.categories.reduce((t, c) => t + c.count, 0)).toBe(KNW01_COUNTS_V6.all);
    expect(ENGAGEMENT_TEMPLATE_CARDS).toHaveLength(6);
    expect(KNW01_COUNTS_V6.categories[0].count).toBe(ENGAGEMENT_TEMPLATE_CARDS.length);
  });
  it("KNW-03 g: four steps carry a rule (two distinct rules), BH-FS-430 the skill", () => {
    expect(FS_V6_RULE_ROWS.filter((r) => r.rules > 0)).toHaveLength(4);
    expect(new Set(FS_V6_RULE_ROWS.map((r) => r.rule).filter((r) => r !== null)).size).toBe(2);
    expect(FS_V6_RULE_ROWS.find((r) => r.skill !== null)?.ref).toBe("BH-FS-430");
    expect(scopingRules().items).toHaveLength(6);
  });
});
