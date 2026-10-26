// POR-14 a–f: every artboard of the handoff, from the scenarios R-01-T05 wrote
// (fixtures/scenarios/POR-14.ts).
import { ARTBOARD, type Por14State, scenarios as all } from "../../fixtures/scenarios/POR-14";

export const scenarios = all;

export type { Por14State };

export const STATES = Object.keys(scenarios) as Por14State[];

export { ARTBOARD };
