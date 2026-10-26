// CLI-07 a–g (P-07-T46): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/CLI-07.ts; each also names the client and engagement it opens.
export {
  type Cli07Options,
  type Cli07State,
  NOTES,
  OPENS,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/CLI-07";
import { type Cli07State, scenarios } from "../../fixtures/scenarios/CLI-07";

export const STATES = Object.keys(scenarios) as Cli07State[];
