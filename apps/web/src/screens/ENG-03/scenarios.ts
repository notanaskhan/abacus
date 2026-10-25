// ENG-03 a–h (P-07-T21 a, b, c, d, f; P-07-T34 e, g, h): one scenario per artboard. The data and
// handlers live under fixtures/scenarios/ENG-03.ts; each also names the draft it opens, and e its
// fixture-only §7216 consents card (until C19).
export {
  CLOCK_AUG_24,
  CLOCK_MAY_11,
  CLOCK_SEP_14,
  CLOCK_SEP_14_951,
  CLOCK_SEP_8,
  CONSENTS,
  type Eng03State,
  FERRIS_DUPLICATE,
  OPENS,
  TYPES,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/ENG-03";
import { type Eng03State, scenarios } from "../../fixtures/scenarios/ENG-03";

export const STATES = Object.keys(scenarios) as Eng03State[];
