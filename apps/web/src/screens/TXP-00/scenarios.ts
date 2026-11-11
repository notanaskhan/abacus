// TXP-00 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-00.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-00";

export { scenarios };

export type Txp00State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp00State[];
