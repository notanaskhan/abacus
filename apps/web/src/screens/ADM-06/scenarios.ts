// ADM-06 a–j (G-02-T16): one scenario per artboard and T03's states; the data and handlers live
// under fixtures/scenarios/ADM-06.ts. OPENS is the search each state opens with; ENTERPRISE is
// revision R2's fixture-only data for i and j (never passed by the route).
import { ENTERPRISE, OPENS, scenarios } from "../../fixtures/scenarios/ADM-06";

export { ENTERPRISE, OPENS, scenarios };

export type Adm06State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Adm06State[];
