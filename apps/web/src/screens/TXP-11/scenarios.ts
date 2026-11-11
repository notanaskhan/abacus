// TXP-11 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-11.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-11";

export { scenarios };

export type Txp11State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp11State[];
