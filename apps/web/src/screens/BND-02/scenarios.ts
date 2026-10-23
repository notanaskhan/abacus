// BND-02 a–f (P-06-T12; P-06 §5.4): one scenario per artboard this task builds, all at E0, Mon Sep
// 14, 2026, 9:24 AM CT, seen by Kevin Osei. The data and handlers live under
// fixtures/scenarios/BND-02.ts; each artboard also names the binder and the request it opens on.
export { BINDERS, type Bnd02State, OPENS, scenarios } from "../../fixtures/scenarios/BND-02";
import { type Bnd02State, scenarios } from "../../fixtures/scenarios/BND-02";

export const STATES = Object.keys(scenarios) as Bnd02State[];
