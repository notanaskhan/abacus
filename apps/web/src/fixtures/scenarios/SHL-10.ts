// SHL-10 a, b, c, f (P-04-T41) and d, e, e′ ("ep"), g (P-04-T42): one scenario per frame built, from the C3 fixtures
// (seed/review.ts, P-04-T34). Each frame names the proposal it opens and the mode it opens in:
// b is a's proposal in edit mode.
import type { Scenario } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import { SHL10 } from "../seed/review";

export const STATES = ["a", "b", "c", "d", "e", "ep", "f", "g"] as const;
export type Shl10State = (typeof STATES)[number];

const all = reviewScenarios("SHL-10");

export const scenarios = Object.fromEntries(STATES.map((s) => [s, all[s] as Scenario])) as Record<
  Shl10State,
  Scenario
>;

export const OPENS: Record<Shl10State, { ref: string; mode: "view" | "edit" | "reject" }> = {
  a: { ref: SHL10.a.ref, mode: "view" },
  b: { ref: SHL10.a.ref, mode: "edit" },
  c: { ref: SHL10.c.ref, mode: "view" },
  d: { ref: SHL10.d.ref, mode: "view" },
  e: { ref: SHL10.e.ref, mode: "view" },
  ep: { ref: SHL10.e_prime.ref, mode: "view" },
  f: { ref: SHL10.f.ref, mode: "view" },
  g: { ref: SHL10.g.ref, mode: "view" },
};
