// ADM-07 a–g (G-02-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/ADM-07.ts. OPENS is the search each state opens with.
import { OPENS, scenarios } from "../../fixtures/scenarios/ADM-07";

export { OPENS, scenarios };

export type Adm07State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Adm07State[];
