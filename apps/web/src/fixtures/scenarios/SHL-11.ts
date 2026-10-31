// SHL-11 a to h: one scenario per frame, from the C3 stub-2 frames (seed/review.ts). a, b, c, d, f,
// g and h are the sheet (P-04-T50); e is the inline dock card over the same card (P-04-T52).
import type { Scenario } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import { CARD_ID } from "../seed/review";

export const STATES = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;
export type Shl11State = (typeof STATES)[number];

const all = reviewScenarios("SHL-11");
export const scenarios = Object.fromEntries(STATES.map((s) => [s, all[s] as Scenario])) as Record<
  Shl11State,
  Scenario
>;
export { CARD_ID };
