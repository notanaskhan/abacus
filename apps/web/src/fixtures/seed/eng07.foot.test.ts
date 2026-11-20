// T-08-T15: the ENG-07 seed foots (ADR-050: the browser never computes; the seed is checked here).
import { describe, expect, it } from "vitest";
import { manifest } from "./eng07";

describe("ENG-07 seed", () => {
  it("cohorts foot to 214 · 224 · 241 and created 126", () => {
    const m = manifest();
    const sum = (k: "engagements" | "returns" | "binders" | "created_rows"): number =>
      m.cohorts.reduce((t, c) => t + (c[k] ?? 0), 0);
    expect([sum("engagements"), sum("returns"), sum("binders")]).toEqual([
      m.tally.engagements,
      m.tally.returns,
      m.tally.binders,
    ]);
    expect(sum("created_rows")).toBe(m.tally.created);
    expect(m.offices.reduce((t, o) => t + o.returns, 0)).toBe(m.tally.returns);
  });
});
