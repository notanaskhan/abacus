// K-03-T08: the TV-1 slice foots (ADR-050): Added 3 + Changed 5 + Removed 0 = 8; 3 + 0 + 3 = 6 live.
import { describe, expect, it } from "vitest";
import { CHANGES, rollout, version } from "./templates-v2";

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
});
