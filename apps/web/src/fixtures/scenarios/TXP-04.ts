// TXP-04 fixture scenarios (T-06-T23, DEC-5636; T-06-T30, TASK-8752; docs/screens/TXP-04.md): one
// per artboard, with the contract's persona and demo clock, over the Ridgeline book-tax seed
// (seed/tax-depth-booktax). d stands on the accepted fix (the workbook after Run 3, the M-2 issue's
// fix applied); the frame, the M-1 toggle and the M-2 variant are the URL's (`opens`).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { type DepthOptions, taxDepthHandlers } from "../handlers/tax-depth";
import type { Snapshot } from "../seed/tax-entity";

function at(
  state: string,
  persona: string,
  clock: string,
  snapshot: Snapshot,
  options: DepthOptions = {},
): Scenario {
  return { state, persona, clock, handlers: taxDepthHandlers(snapshot, options) };
}

export const scenarios = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // M-3 (one permanent row 6,200) · `ridgeline-e0`
  ap: at("ap", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // M-1 reference toggle (file `TXP-04ap.png`) · `ridgeline-e0`
  b: at("b", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // M-2 as drafted (6,860,000 vs 6,866,200) · `ridgeline-e0`
  c: at("c", "samuel-ito", "2026-09-14T09:24:00-05:00", "run2"), // With proposed fix (tie) · `ridgeline-e0`
  d: at("d", "samuel-ito", "2026-09-14T09:51:00-05:00", "afterFix", {
    bookTax: "accepted",
    issues: "d",
  }), // Accepted (Approved by Samuel Ito · 9:51 AM) · `ridgeline-m2-accepted`
});

export type Txp04State = keyof typeof scenarios;

/** The search each artboard opens on: the M-1 toggle and the M-2 variant. */
export const TXP04_OPENS: Readonly<Record<string, string>> = {
  ap: "?m1=1",
  c: "?variant=with_fix",
};

/** The review tab each artboard draws (one screen ID, two Group B frames). */
export const TXP04_REVIEW: Readonly<Record<string, "m1-m3" | "schedule-m2">> = {
  a: "m1-m3",
  ap: "m1-m3",
  b: "schedule-m2",
  c: "schedule-m2",
  d: "schedule-m2",
};
