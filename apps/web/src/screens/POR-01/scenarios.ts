// POR-01 (P-08-T08, T09, T19): every artboard, a to g, the DF-17 setup state c2 (c′) and the 390
// layout M, on the scenarios in fixtures/scenarios/POR-01.ts.
import { START, scenarios as all } from "../../fixtures/scenarios/POR-01";

export const scenarios = {
  a: all.a,
  b: all.b,
  c: all.c,
  c2: all.c2,
  d: all.d,
  e: all.e,
  f: all.f,
  g: all.g,
  M: all.M,
};

export type Por01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por01State[];

export { START };
