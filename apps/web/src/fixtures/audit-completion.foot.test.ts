// A-07-T11 (TASK-3318): the seven screens' fixture states foot. Row: "/components/screens/AUD-25?st=c
// &frame=1&static=1 reproduces the Thu Dec 3, 2026 4:18 PM CST locked state with seal 7c41…a9e2 from
// typed data." The route joins with AUD-25's screen (A-07-T39); the state is pinned here.
import { describe, expect, it } from "vitest";
import { STATES as AUD18 } from "./scenarios/AUD-18";
import { STATES as AUD19 } from "./scenarios/AUD-19";
import { STATES as AUD21 } from "./scenarios/AUD-21";
import { STATES as AUD22 } from "./scenarios/AUD-22";
import { STATES as AUD23 } from "./scenarios/AUD-23";
import { STATES as AUD24 } from "./scenarios/AUD-24";
import { scenarios as aud25scenarios, STATES as AUD25 } from "./scenarios/AUD-25";
import { aud18, aud19, aud24, aud25, SEAL } from "./seed/audit-completion";

describe("A-07 fixture states", () => {
  it("every one of the 49 artboards has a scenario", () => {
    expect(
      [AUD18, AUD19, AUD21, AUD22, AUD23, AUD24, AUD25].map((states) => states.length),
    ).toEqual([6, 7, 7, 7, 10, 6, 6]);
  });

  it("AUD-18 a reads 6 of 10, d concurred at 10 of 10", () => {
    expect([aud18("a").checklist_done, aud18("a").checklist_total]).toEqual([6, 10]);
    expect(aud18("d").checklist_done).toBe(10);
    expect(aud18("e").allowed_actions).toEqual([]);
  });

  it("AUD-19 foots: complete + open = total, not applicable excluded", () => {
    for (const state of ["a", "e", "f"] as const) {
      const row = aud19(state);
      expect(row.complete + row.open).toBe(row.total);
    }
    expect(aud19("a").complete).toBe(12);
  });

  it("AUD-24 releases only with G5 to G7 met", () => {
    expect(aud24("a").can_release).toBe(true);
    expect(aud24("b").can_release).toBe(false);
    expect(aud24("e").viewer_can_release).toBe(false);
  });

  it("AUD-25 c is the Dec 3, 4:18 PM CST lock with the seal", () => {
    const locked = aud25("c");
    const seal = locked.seal_sha256 ?? "";
    expect(`${seal.slice(0, 4)}…${seal.slice(-4)}`).toBe("7c41…a9e2");
    expect(seal).toBe(SEAL);
    expect(locked.locked_at).toBe("2026-12-03T16:18:00-06:00");
    expect(locked.documentation_completion_date).toBe("2026-12-08");
    expect(aud25scenarios.c.clock).toBe("2026-12-03T16:18:00-06:00");
    expect(aud25("c").allowed_actions).toEqual([]);
  });
});
