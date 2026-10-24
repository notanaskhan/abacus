// POR-03 a, c, e, f, g and h (R-01-T06, part 1): the artboards part 1 builds, from the scenarios
// R-01-T05 wrote (fixtures/scenarios/POR-03.ts). b, motion, c2, d, i and M are R-01-T10's.
import { ARTBOARD, scenarios as all } from "../../fixtures/scenarios/POR-03";

export const scenarios = { a: all.a, c: all.c, e: all.e, f: all.f, g: all.g, h: all.h } as const;

export type Por03State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por03State[];

export { ARTBOARD };
