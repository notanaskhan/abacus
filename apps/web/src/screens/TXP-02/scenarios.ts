// TXP-02 artboards (T-05-T13): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/TXP-02.ts.
import { scenarios } from "../../fixtures/scenarios/TXP-02";

export { scenarios };

export type Txp02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Txp02State[];
