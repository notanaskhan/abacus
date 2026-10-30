// KNW-03 a, b and e (K-01-T13): the data and handlers live under fixtures/scenarios/KNW-03.ts.
import { type Knw03State, OPENS, scenarios } from "../../fixtures/scenarios/KNW-03";

export { type Knw03State, OPENS, scenarios };

export const STATES = Object.keys(scenarios) as Knw03State[];
