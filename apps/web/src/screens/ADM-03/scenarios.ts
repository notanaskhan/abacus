// ADM-03 a–h (G-01-T14): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/ADM-03.ts. OPENS is the search (and anchor) each state opens with.
import { OPENS, scenarios } from "../../fixtures/scenarios/ADM-03";

export { OPENS, scenarios };

export type Adm03State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Adm03State[];
