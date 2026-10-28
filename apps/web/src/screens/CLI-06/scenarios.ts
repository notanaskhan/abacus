// CLI-06 a–i: one scenario per artboard, the single intake (P-07-T49) and g, the bulk import
// (P-07-T54). The data and handlers live under fixtures/scenarios/CLI-06.ts.
export {
  type Cli06State,
  DRAFT_ID,
  IMPORT_ID,
  OPENS,
  THORNBURY_CLIENT,
  freshScenario,
  importRows,
  scenarios,
} from "../../fixtures/scenarios/CLI-06";
import { type Cli06State, scenarios } from "../../fixtures/scenarios/CLI-06";

export const STATES = Object.keys(scenarios) as Cli06State[];
