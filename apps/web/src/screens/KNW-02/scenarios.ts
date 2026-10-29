// KNW-02 e and f (K-01-T07): the workbook slice's scenarios; data and handlers live under
// fixtures/scenarios/KNW-02.ts.
import { OPENS, scenarios } from "../../fixtures/scenarios/KNW-02";

export { OPENS, scenarios };

export type Knw02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Knw02State[];
