// POR-03 a–i, motion, c2 and M: every artboard of the handoff, from the scenarios R-01-T05 wrote
// (fixtures/scenarios/POR-03.ts). Part 1 (R-01-T06) built a, c, e, f, g and h; part 2 (R-01-T10)
// b, motion, c from polling, c2, d, i and M.
import { ARTBOARD, scenarios as all } from "../../fixtures/scenarios/POR-03";

export const scenarios = all;

export type Por03State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por03State[];

export { ARTBOARD };
