// SHL-14 a, b, e, f (P-06-T13) and d (P-06-T24): one scenario per state built. The data and
// handlers live under fixtures/scenarios/SHL-14.ts; each state also names the binder and the
// request it opens (null composes a new one).
export {
  CLOCK_A,
  CLOCK_F,
  OPENS,
  type Shl14State,
  scenarios,
} from "../../fixtures/scenarios/SHL-14";
import { type Shl14State, scenarios } from "../../fixtures/scenarios/SHL-14";

export const STATES = Object.keys(scenarios) as Shl14State[];
