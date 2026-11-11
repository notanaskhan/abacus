// TXP-05 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-05.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-05";

export { scenarios };

export type Txp05State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp05State[];
