// C-02-T15 (DEC-5624): the 37 CLS-07, CLS-08, CLS-11, CLS-12 and CLS-13 artboards each have a
// scenario with a seated persona and an instant with its offset (CDT, then CST from Nov 1, 2026).
import { describe, expect, it } from "vitest";
import { SEATS, slugOf } from "../seed/people";
import { scenarios as cls07 } from "./CLS-07";
import { scenarios as cls08 } from "./CLS-08";
import { scenarios as cls11 } from "./CLS-11";
import { scenarios as cls12 } from "./CLS-12";
import { scenarios as cls13 } from "./CLS-13";

const ALL = {
  "CLS-07": cls07,
  "CLS-08": cls08,
  "CLS-11": cls11,
  "CLS-12": cls12,
  "CLS-13": cls13,
};
const SEATED = new Set(SEATS.map((s) => slugOf(s.name)));

describe("C-02 screen scenarios", () => {
  it("cover 37 artboards: 9 + 8 + 8 + 5 + 7", () => {
    expect(Object.values(ALL).map((s) => Object.keys(s).length)).toEqual([9, 8, 8, 5, 7]);
  });

  it("each has a seated persona and an offset instant", () => {
    for (const set of Object.values(ALL)) {
      for (const s of Object.values(set)) {
        expect(SEATED.has(s.persona ?? "")).toBe(true);
        expect(s.clock).toMatch(/^20\d\d-\d\d-\d\dT\d\d:\d\d:00-0[56]:00$/);
      }
    }
  });

  it("CLS-07 c, c2 and d are Priya Raman's; CLS-12a is Tue Jan 12, 2027, 2:15 PM CST", () => {
    expect([cls07.c.persona, cls07.c2.persona, cls07.d.persona]).toEqual([
      "priya-raman",
      "priya-raman",
      "priya-raman",
    ]);
    expect(cls12.a.clock).toBe("2027-01-12T14:15:00-06:00");
  });
});
