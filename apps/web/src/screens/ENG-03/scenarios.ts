// ENG-03 a, b, c, d, f (P-07-T21): one scenario per artboard this task builds. The data and
// handlers live under fixtures/scenarios/ENG-03.ts; each also names the draft it opens.
export {
  CLOCK_AUG_24,
  CLOCK_SEP_8,
  type Eng03State,
  OPENS,
  TYPES,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/ENG-03";
import { type Eng03State, scenarios } from "../../fixtures/scenarios/ENG-03";

export const STATES = Object.keys(scenarios) as Eng03State[];
