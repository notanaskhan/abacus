// HOME-02 a–g and the catalogue states (I-01-T15): the data and handlers live under
// fixtures/scenarios/HOME-02.ts; I-01-T16 renders the queue of each.
import { type Home02State, scenarios } from "../../fixtures/scenarios/HOME-02";

export { type Home02State, scenarios };

export const STATES = Object.keys(scenarios) as Home02State[];
