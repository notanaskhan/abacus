// ADM-04 a–j, band, awaiting, real_firm (G-02-T25): one scenario per artboard; the data and
// handlers live under fixtures/scenarios/ADM-04.ts. OPENS is what each state opens with.
import { type Adm04State, OPENS, scenarios } from "../../fixtures/scenarios/ADM-04";

export { OPENS, scenarios };
export type { Adm04State };

export const STATES = Object.keys(scenarios) as Adm04State[];
