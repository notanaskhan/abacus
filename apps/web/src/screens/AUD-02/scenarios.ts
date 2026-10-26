// AUD-02 a–g (A-01-T12; f A-01-T31): one scenario per artboard built. The data and handlers live
// under fixtures/scenarios/AUD-02.ts; OPENS names the rail row and dock each artboard opens on (d
// selects Materiality, blocked on Margaret Okonkwo) and f opens with the Auto mode confirm.
import {
  AUDIT_ID,
  AUTO_MODE_ROUTE,
  autoModeRefused,
  scenarios,
} from "../../fixtures/scenarios/AUD-02";
import type { AutoModeStep } from "../../domain/audits";
import type { DockTab } from ".";

export { AUDIT_ID, AUTO_MODE_ROUTE, autoModeRefused, scenarios };

export type Aud02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Aud02State[];

export const OPENS: Readonly<
  Record<
    Aud02State,
    { section?: string; dock?: DockTab; doc?: string | null; autoMode?: AutoModeStep }
  >
> = {
  a: {},
  b: {},
  c: {},
  d: { section: "materiality" },
  e: {},
  f: { autoMode: "asking" },
  g: {},
};
