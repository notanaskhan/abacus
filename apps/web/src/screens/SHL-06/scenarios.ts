// SHL-06 g and the sign-in error state (P-01-T11): the scenarios live under fixtures/scenarios/
// and are re-exported here for the screen's tests and the gallery.
export { SEARCH, type Shl06State, scenarios } from "../../fixtures/scenarios/SHL-06";
import { type Shl06State, scenarios } from "../../fixtures/scenarios/SHL-06";

export const STATES = Object.keys(scenarios) as Shl06State[];
