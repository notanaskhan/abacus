// SHL-03 a–f (P-01 §5.3): one scenario per artboard, each its README viewer at Mon 14 Sep 2026,
// 9:24 AM CT. The data is fixtures/seed/shell.ts (P-01-T07); the scenarios themselves stay beside
// it under fixtures/scenarios/ and are re-exported here for the screen's tests and the gallery.
export { scenarios } from "../../fixtures/scenarios/SHL-03";
import { scenarios } from "../../fixtures/scenarios/SHL-03";

export type Shl03State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Shl03State[];
