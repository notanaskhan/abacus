// SHL-12 a, a′ ("ap"), b, c, d, e, g, h (P-04-T48): one scenario per frame built, from the C3
// stub-1 fixtures (seed/review.ts, P-04-T34). Each frame names the target and the level it opens
// at; f (bulk, P-04-T49) opens on the six workpapers Hannah picked (BULK_TARGET_IDS).
import type { Scenario } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import { BULK_TARGET_IDS, RIDGELINE_RETURN, TB } from "../seed/review";

/** SHL-12 f: the bulk sheet's six workpapers, in order. */
export const BULK = BULK_TARGET_IDS.map((id) => ({ type: "workpaper", id }));

export const STATES = ["a", "ap", "b", "c", "d", "e", "f", "g", "h"] as const;
export type Shl12State = (typeof STATES)[number];

const all = reviewScenarios("SHL-12");

export const scenarios = Object.fromEntries(STATES.map((s) => [s, all[s] as Scenario])) as Record<
  Shl12State,
  Scenario
>;

type Level = "L1_preparer" | "L2_reviewer" | "L3_manager" | "L4_partner" | "L5_eqr";

export const OPENS: Record<Shl12State, { type: string; id: string; level: Level; meta: string }> =
  {
    a: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "AUD-06" },
    ap: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "AUD-06" },
    b: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "AUD-06" },
    c: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "AUD-06" },
    d: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "AUD-06" },
    e: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "AUD-06" },
    f: { type: "workpaper", id: TB, level: "L2_reviewer", meta: "Northwind · PY2025" },
    g: { type: "workpaper", id: TB, level: "L5_eqr", meta: "AUD-06" },
    h: {
      type: "tax_return",
      id: RIDGELINE_RETURN,
      level: "L4_partner",
      meta: "2025 Form 1065 · Ridgeline",
    },
  };
