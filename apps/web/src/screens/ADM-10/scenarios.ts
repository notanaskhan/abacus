// ADM-10 a–g (R-01-T28): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/ADM-10.ts. OPENS is the search each state opens with; PREVIEW_AS the contacts
// "Preview as" lists.
import { OPENS, PREVIEW_AS, scenarios } from "../../fixtures/scenarios/ADM-10";

export { OPENS, PREVIEW_AS, scenarios };

export type Adm10State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Adm10State[];
