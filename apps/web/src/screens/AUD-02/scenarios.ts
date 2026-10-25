// AUD-02 a–e, g (A-01-T12): one scenario per artboard this task builds. The data and handlers live
// under fixtures/scenarios/AUD-02.ts; OPENS names the rail row and dock each artboard opens on (d
// selects Materiality, blocked on Margaret Okonkwo).
import { AUDIT_ID, scenarios } from "../../fixtures/scenarios/AUD-02";
import type { DockTab } from ".";

export { AUDIT_ID, scenarios };

export type Aud02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Aud02State[];

export const OPENS: Readonly<
  Record<Aud02State, { section?: string; dock?: DockTab; doc?: string | null }>
> = {
  a: {},
  b: {},
  c: {},
  d: { section: "materiality" },
  e: {},
  g: {},
};
