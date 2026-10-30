// TAX-02 a–f (T-02-T14): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/TAX-02.ts; each artboard also names the return it opens.
import { ENTITY_RETURN, OPENS, scenarios } from "../../fixtures/scenarios/TAX-02";

export { ENTITY_RETURN, OPENS, scenarios };

export type Tax02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Tax02State[];
