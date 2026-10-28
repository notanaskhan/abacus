// ENG-13 a–e (P-07-T60): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/ENG-13.ts; each names the source and draft it opens, its first step, and the
// fixture-only preview the handoff draws.
export {
  CLOCK_JAN_11,
  CLOCK_NOV_16,
  CLOCK_NOV_16_11,
  type Eng13State,
  OPENS,
  PREVIEWS,
  STEP_OF,
  draftOf,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/ENG-13";
import { type Eng13State, scenarios } from "../../fixtures/scenarios/ENG-13";

export const STATES = Object.keys(scenarios) as Eng13State[];
