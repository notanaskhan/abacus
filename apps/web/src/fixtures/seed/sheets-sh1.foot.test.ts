// K-03-T09: the SH-1 slice foots: 24 + 16 = 40 rows, 3,698,700.00, and 31 + 8 + 1 + 0 = 40.
import { describe, expect, it } from "vitest";
import { SURL_SHEET } from "./granite-peak-fy2026-surl-sheet";
import { CONCLUSIONS, sheet } from "./sheets-sh1";

describe("SH-1 seed", () => {
  it("the strata foot to 40 rows and 3,698,700.00", () => {
    const s = sheet();
    expect(s.sections.reduce((t, x) => t + x.count, 0)).toBe(s.status.rows);
    expect(SURL_SHEET.sections.reduce((t, x) => t + x.total, 0)).toBe(3698700);
  });
  it("the conclusions add to 40", () => {
    expect(Object.values(CONCLUSIONS).reduce((t, n) => t + n, 0)).toBe(sheet().status.rows);
  });
});
