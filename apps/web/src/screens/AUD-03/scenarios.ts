// AUD-03 a–g (A-01-T15): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/AUD-03.ts; OPENS names the row each artboard opens on (d with "Return…").
import {
  ANA_ACTIONS,
  AUDIT_ID,
  type Aud03Options,
  type Aud03State,
  ENGAGEMENT_ID,
  OPENS,
  itemOf,
  scenarioFor,
  scenarios,
} from "../../fixtures/scenarios/AUD-03";

export {
  ANA_ACTIONS,
  AUDIT_ID,
  type Aud03Options,
  type Aud03State,
  ENGAGEMENT_ID,
  OPENS,
  itemOf,
  scenarioFor,
  scenarios,
};

export const STATES = Object.keys(scenarios) as Aud03State[];
