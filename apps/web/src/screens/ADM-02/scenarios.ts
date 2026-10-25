// ADM-02 a–g (G-01-T10): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/ADM-02.ts (G-01-T06). OPENS is the search each state opens with.
import { OPENS, scenarios } from "../../fixtures/scenarios/ADM-02";

export { OPENS, scenarios };

export type Adm02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Adm02State[];
