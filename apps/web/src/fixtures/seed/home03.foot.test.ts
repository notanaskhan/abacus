// T-08-T16: the HOME-03 seed holds the handoff's counts (Sep 15: 12 items; Daniel Reyes: 5).
import { describe, expect, it } from "vitest";
import { calendar } from "./home03";

describe("HOME-03 seed", () => {
  it("Sep 15 lists 12 items, three shown", () => {
    const sep15 = (calendar().days ?? []).find((d) => d.on === "2026-09-15");
    expect(sep15?.total).toBe(12);
    expect(sep15?.shown).toHaveLength(3);
  });
  it("Daniel Reyes's filter keeps five", () => {
    expect(calendar("daniel").items).toHaveLength(5);
  });
  it("every item has an owner and words for its risk", () => {
    for (const i of calendar().items) {
      expect(i.owners.length).toBeGreaterThan(0);
      expect(i.risk_label.length).toBeGreaterThan(0);
    }
  });
});
