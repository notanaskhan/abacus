// POR-13 a–f (T-02-T27): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/POR-13.ts.
import { OPENING, type Por13State, scenarios } from "../../fixtures/scenarios/POR-13";

export { OPENING, scenarios };
export type { Por13State };

export const STATES = Object.keys(scenarios) as Por13State[];
