// HOME-01 (I-01-T05): one scenario per artboard and state; the data and handlers live under
// fixtures/scenarios/HOME-01.ts. office-denver opens with the Office chip on Denver.
import { OFFICE, scenarios } from "../../fixtures/scenarios/HOME-01";

export { OFFICE, scenarios };

export type Home01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Home01State[];
