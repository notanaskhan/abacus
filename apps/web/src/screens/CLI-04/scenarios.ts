// CLI-04 a–g (P-07-T33): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/CLI-04.ts; each also names the client it opens and the overlay it opens on.
export {
  COPPERLEAF_ID,
  type Cli04State,
  HARBORLINE,
  NORTHWIND_ID,
  OPENS,
  OVERLAYS,
  SAM_ORTIZ,
  SUMMIT,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/CLI-04";
import { type Cli04State, scenarios } from "../../fixtures/scenarios/CLI-04";

export const STATES = Object.keys(scenarios) as Cli04State[];
