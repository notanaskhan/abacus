// INB-01's artboards (N-01-T10): N-01-T10's fixture scenarios and the thread each opens.
export { OPENS, scenarios } from "../../fixtures/scenarios/INB-01";
export const STATES = ["a", "b", "c", "d", "e", "f", "g"] as const;
export type Inb01State = (typeof STATES)[number];
