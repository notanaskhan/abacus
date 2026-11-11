// TXP-10 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-10.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-10";

export { scenarios };

export type Txp10State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp10State[];
