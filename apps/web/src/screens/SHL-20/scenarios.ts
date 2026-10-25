// SHL-20 a–f (P-06-T22): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/SHL-20.ts.
export {
  OPENS,
  type Shl20Opens,
  type Shl20State,
  scenarios,
  screeningHandlers,
} from "../../fixtures/scenarios/SHL-20";
import { type Shl20State, scenarios } from "../../fixtures/scenarios/SHL-20";

export const STATES = Object.keys(scenarios) as Shl20State[];
