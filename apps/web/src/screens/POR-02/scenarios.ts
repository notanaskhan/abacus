// POR-02 a, b, c, f (P-08-T15): the artboards part 1 builds, from the scenarios P-08-T08 wrote
// (fixtures/scenarios/POR-02.ts; d, e and M are P-08-T23's, g and h arrive with their epochs).
import { scenarios as all } from "../../fixtures/scenarios/POR-02";

export { FIRST_VISIT_CLOCK, feldOpenUploads } from "../../fixtures/scenarios/POR-02";

export const scenarios = { a: all.a, b: all.b, c: all.c, f: all.f } as const;

export type Por02State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por02State[];
