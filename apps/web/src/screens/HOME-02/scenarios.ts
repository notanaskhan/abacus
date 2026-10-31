// HOME-02 a–g and the catalogue states (I-01-T15): the data and handlers live under
// fixtures/scenarios/HOME-02.ts; I-01-T16 renders the queue of each, I-01-T17 the detail of the row
// each artboard selects (b the decided §754 card, c Capital Accounts, d the memo, g the Feld
// classification).
import { type Home02State, scenarios, selectedGate } from "../../fixtures/scenarios/HOME-02";

export { type Home02State, scenarios, selectedGate };

export const STATES = Object.keys(scenarios) as Home02State[];
