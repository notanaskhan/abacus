// T-02-T08 (SPEC-502 AC-9): TAX-01's summary foots, and every T-02 artboard has a scenario.
import { describe, expect, it } from "vitest";
import { por05, por13, tax01, tax02, tax03, txp12 } from "./scenarios/tax-returns";
import { OPEN_STATUSES, TY2025_SUMMARY } from "./seed/tax-returns";

describe("T-02 fixture figures", () => {
  it("TAX-01: 79 open + 145 done = 224 TY2025 returns", () => {
    const s = TY2025_SUMMARY;
    const open = s.tiles.filter((t) => OPEN_STATUSES.has(t.status));
    const done = s.tiles.filter((t) => !OPEN_STATUSES.has(t.status));
    expect(open.reduce((t, x) => t + x.count, 0)).toBe(79);
    expect(done.reduce((t, x) => t + x.count, 0)).toBe(145);
    expect(s.open + s.done).toBe(s.total);
    expect(s.total).toBe(224);
  });

  it("TAX-01 c: offices foot to the tiles (98/35/63, 64/22/42, 62/22/40)", () => {
    const offices = TY2025_SUMMARY.offices;
    expect(offices.map((o) => o.open + o.done)).toEqual([98, 64, 62]);
    expect(offices.reduce((t, o) => t + o.open, 0)).toBe(79);
    expect(offices.reduce((t, o) => t + o.done, 0)).toBe(145);
  });

  it("names the 43 built artboards", () => {
    const counts = [tax01, tax02, tax03, txp12, por05, por13].map((s) => Object.keys(s).length);
    expect(counts.reduce((t, n) => t + n, 0)).toBe(43);
    expect(por13.b.persona).toBe("pell-street-member");
  });
});
