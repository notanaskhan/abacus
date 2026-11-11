// S35 follow-up (TASK-6741; DEC-3306): fixture mode's AUD-24 a against the release read exported
// from `make seed-demo --slice archive` at the report date's 10:05 AM
// (`make fixtures SNAPSHOT=2026-10-09T10:05`; two exports are byte-identical). What both sides
// must agree on: G5 to G7 met, the release open to the EP, and every also-required row met.
//
// Known gaps, pinned so a new one fails (TASK-6741):
// - the load reads G8 too (not yet released), which fixture mode leaves out;
// - the load lists two more also-required rows (final materiality, the AU-C 260 letter), which
//   the design does not draw;
// - the values are the load's own words: the FS's approved version ("v3", not the design's date),
//   the bring-down with no run number (the run's time is the database's, DEC-3306) and the
//   team's six confirmations (the design counts five).
import type { AuditReleaseOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { aud24 } from "./audit-completion";
import exported from "./2026-10-09t1005.northwind-release.json";

const loaded = (exported as { body: unknown }).body as AuditReleaseOut;
const fixture = aud24("a");

describe("AUD-24 a: fixture mode against the 10:05 load", () => {
  it("both read G5 to G7 met and the release open to the EP", () => {
    const met = (r: AuditReleaseOut) =>
      Object.fromEntries(r.gates.filter((g) => g.gate !== "G8").map((g) => [g.gate, g.met]));
    expect(met(loaded)).toEqual(met(fixture));
    expect(loaded.gates.find((g) => g.gate === "G8")?.met).toBe(false);
    expect(loaded.can_release).toBe(fixture.can_release);
    expect(loaded.viewer_can_release).toBe(fixture.viewer_can_release);
    expect(loaded.released_at).toBeNull();
  });

  it("every also-required row the design draws is met on both sides", () => {
    const keys = fixture.also_required.map((a) => a.key);
    const byKey = new Map(loaded.also_required.map((a) => [a.key, a]));
    for (const key of keys) expect(byKey.get(key)?.met).toBe(true);
    expect([...byKey.keys()].filter((k) => !keys.includes(k))).toEqual([
      "final_materiality",
      "governance_260",
    ]);
    expect(Object.fromEntries(keys.map((k) => [k, byKey.get(k)?.value ?? null]))).toEqual({
      fs_approved: "v3",
      bring_down: null,
      independence: "6 of 6",
    });
  });
});
