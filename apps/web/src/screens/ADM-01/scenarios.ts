// ADM-01 a–f (G-01-T07): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/ADM-01.ts (G-01-T06). b, c and f are reached by editing a.
import { scenarios } from "../../fixtures/scenarios/ADM-01";

export { scenarios };

export type Adm01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Adm01State[];
