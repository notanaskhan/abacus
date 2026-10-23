// CLI-02 a, a2, b, c, e, f (P-07-T19): one scenario per artboard this task builds. The data and
// handlers live under fixtures/scenarios/CLI-02.ts; each artboard also names the client it opens.
export {
  type Cli02State,
  OCT_1,
  OPENS,
  metadataOnlyHandlers,
  scenarios,
} from "../../fixtures/scenarios/CLI-02";
import { type Cli02State, scenarios } from "../../fixtures/scenarios/CLI-02";

export const STATES = Object.keys(scenarios) as Cli02State[];
