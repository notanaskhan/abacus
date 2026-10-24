// ENG-02 a–g and the prospect state (P-07-T20, P-07-T28): one scenario per state.
// The data and handlers live under fixtures/scenarios/ENG-02.ts; each also names the engagement
// it opens and the tab it opens on.
export { type Eng02State, OPENS, TABS, scenarios } from "../../fixtures/scenarios/ENG-02";
import { type Eng02State, scenarios } from "../../fixtures/scenarios/ENG-02";

export const STATES = Object.keys(scenarios) as Eng02State[];
