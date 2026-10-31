// POR-06 a to h, the return before the server says signed, restricted and the list: the
// scenarios N-02-T26 and N-02-T29 wrote (fixtures/scenarios/POR-06.ts).
import { ARTBOARD, type Por06State, scenarios as all } from "../../fixtures/scenarios/POR-06";

export const scenarios = all;

export type { Por06State };

export const STATES = Object.keys(scenarios) as Por06State[];

export { ARTBOARD };
