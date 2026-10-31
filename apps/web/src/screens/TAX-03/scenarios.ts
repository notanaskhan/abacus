// TAX-03 a, a2, b–f (T-02-T19): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/TAX-03.ts; each artboard also names the return it opens.
import { OPENS, OPEN_DOCUMENT, type Tax03State, scenarios } from "../../fixtures/scenarios/TAX-03";

export { OPENS, OPEN_DOCUMENT, scenarios };
export type { Tax03State };

export const STATES = Object.keys(scenarios) as Tax03State[];
