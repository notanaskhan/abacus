// POR-02 a–h and M: every artboard of the handoff, from the scenarios P-08-T08 and P-08-T23 wrote
// (fixtures/scenarios/POR-02.ts). Part 1 (P-08-T15) built a, b, c and f; part 2 (P-08-T23) d, e,
// g, h and M. g and h are fixture-only (the `statements_studio` and `attest` entitlements).
import { scenarios as all } from "../../fixtures/scenarios/POR-02";

export { FIRST_VISIT_CLOCK, feldOpenUploads } from "../../fixtures/scenarios/POR-02";

export const scenarios = all;

export type Por02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por02State[];

/** The artboards drawn at 390 (T7-M). */
export const MOBILE_STATES: ReadonlySet<Por02State> = new Set(["M"]);
