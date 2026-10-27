// POR-16 a–g: every Copperleaf artboard of the handoff, from the scenarios A-02-T06 wrote
// (fixtures/scenarios/POR-16.ts). h and i (Tessellate's HR and ticketing) are X-02's.
import { ARTBOARD, type Por16Scenario, scenarios as all } from "../../fixtures/scenarios/POR-16";

export const scenarios = all;

export type Por16State = Por16Scenario;

export const STATES = Object.keys(scenarios) as Por16State[];

export { ARTBOARD };
