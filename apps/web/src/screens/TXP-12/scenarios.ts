// TXP-12 A–F (T-02-T25): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/TXP-12.ts; each artboard also names the return and opening it starts on.
import {
  OPENING,
  OPENS,
  type Txp12Opening,
  type Txp12State,
  scenarios,
} from "../../fixtures/scenarios/TXP-12";

export { OPENING, OPENS, scenarios };
export type { Txp12Opening, Txp12State };

export const STATES = Object.keys(scenarios) as Txp12State[];
