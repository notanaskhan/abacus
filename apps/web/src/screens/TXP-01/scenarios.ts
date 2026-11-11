// TXP-01 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-01.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-01";

export { scenarios };

export type Txp01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp01State[];
