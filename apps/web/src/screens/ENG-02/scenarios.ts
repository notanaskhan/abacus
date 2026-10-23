// ENG-02 b, c, d, e and the prospect state (P-07-T20): one scenario per state this task builds.
// The data and handlers live under fixtures/scenarios/ENG-02.ts; each also names the engagement
// it opens.
export { type Eng02State, OPENS, scenarios } from "../../fixtures/scenarios/ENG-02";
import { type Eng02State, scenarios } from "../../fixtures/scenarios/ENG-02";

export const STATES = Object.keys(scenarios) as Eng02State[];
