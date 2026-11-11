// TXP-07 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-07.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-07";

export { scenarios };

export type Txp07State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp07State[];
