// TXP-06 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-06.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-06";

export { scenarios };

export type Txp06State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp06State[];
