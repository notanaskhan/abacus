// POR-01 (P-08-T08, T09): the artboards this task builds, a, b, e, f, g and the 390 layout M, on
// the scenarios in fixtures/scenarios/POR-01.ts. c, c2 (c′) and d have scenarios there and are
// built by P-08-T19.
import { START, scenarios as all } from "../../fixtures/scenarios/POR-01";

export const scenarios = { a: all.a, b: all.b, e: all.e, f: all.f, g: all.g, M: all.M };

export type Por01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por01State[];

export { START };
