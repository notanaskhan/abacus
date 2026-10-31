// SHL-11 a, b, c, d, f, g, h (P-04-T50): one scenario per frame built, from the C3 stub-2 frames
// (seed/review.ts). e (the inline dock card) is P-04-T52's.
import type { Scenario } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import { CARD_ID } from "../seed/review";

export const STATES = ["a", "b", "c", "d", "f", "g", "h"] as const;
export type Shl11State = (typeof STATES)[number];

const all = reviewScenarios("SHL-11");
export const scenarios = Object.fromEntries(STATES.map((s) => [s, all[s] as Scenario])) as Record<
  Shl11State,
  Scenario
>;
export { CARD_ID };
