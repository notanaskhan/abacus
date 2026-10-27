// CLI-06 a–f, h and i (P-07-T49): one scenario per single-intake artboard; g is P-07-T54's bulk
// import. The data and handlers live under fixtures/scenarios/CLI-06.ts.
export {
  type Cli06State,
  DRAFT_ID,
  OPENS,
  THORNBURY_CLIENT,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/CLI-06";
import { type Cli06State, scenarios } from "../../fixtures/scenarios/CLI-06";

export const STATES = Object.keys(scenarios) as Cli06State[];
