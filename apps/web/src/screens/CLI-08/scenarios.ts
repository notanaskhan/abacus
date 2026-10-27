// CLI-08 a–g and the declined-note state (P-07-T48): one scenario per artboard. The data and
// handlers live under fixtures/scenarios/CLI-08.ts; each names the tab it opens on.
export {
  CHECK_ID,
  CLIENT_ID,
  type Cli08State,
  ENGAGEMENT_ID,
  OPENS,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/CLI-08";
import { type Cli08State, scenarios } from "../../fixtures/scenarios/CLI-08";

export const STATES = Object.keys(scenarios) as Cli08State[];
