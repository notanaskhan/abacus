// SHL-07 a–e (P-03-T07): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/SHL-07.ts; OPENS names each artboard's popover variant and how it opens.
export {
  KEYSTONE_CELL,
  OPENS,
  RISK_GUIDANCE_REF,
  RISK_WORKPAPER,
  SERVICE_ORGANIZATIONS,
  SERVICE_ORGS_SECTION,
  SERVICE_ORGS_WORKPAPER,
  type Shl07State,
  scenarios,
} from "../../fixtures/scenarios/SHL-07";
import { type Shl07State, scenarios } from "../../fixtures/scenarios/SHL-07";

export const STATES = Object.keys(scenarios) as Shl07State[];
