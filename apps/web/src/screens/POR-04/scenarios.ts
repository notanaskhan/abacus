// POR-04 a–g: every artboard of the handoff, from the scenarios R-01-T05 wrote
// (fixtures/scenarios/POR-04.ts). e and f are the sheet's typed question and decision slots,
// fixture only (C-01 and T-06 / T-09 wire them to their own routes).
import { ARTBOARD, type Por04State, scenarios as all } from "../../fixtures/scenarios/POR-04";

export const scenarios = all;

export type { Por04State };

export const STATES = Object.keys(scenarios) as Por04State[];

export { ARTBOARD };
