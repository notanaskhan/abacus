// POR-23 a–f: every artboard of the handoff, from fixtures/scenarios/POR-23.ts (A-09-T36).
import {
  POR23_CLOCKS,
  type Por23Scenario,
  scenarios as all,
} from "../../fixtures/scenarios/POR-23";

export const scenarios = all;
export type Por23State = Por23Scenario;
export const STATES = Object.keys(scenarios) as Por23State[];
export { POR23_CLOCKS };
