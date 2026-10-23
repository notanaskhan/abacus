// BND-01 a, c, d, e (P-06-T09; P-06 §5.4): one scenario per artboard this task builds, all at E0,
// Mon Sep 14, 2026, 9:24 AM CT. b (Client activity │ None in 30 days, the bulk bar) arrives with
// the follow-up sheet in P-06-T16. The data and handlers live under fixtures/scenarios/BND-01.ts;
// each artboard also names the search params it opens on (d opens on Season │ TY2026).
import type { BinderFilters } from "../../domain/requests";
import { scenarios as all } from "../../fixtures/scenarios/BND-01";

export const scenarios = { a: all.a, c: all.c, d: all.d, e: all.e };

export type Bnd01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Bnd01State[];

/** What each artboard changes from the screen's default filters. */
export const SEARCH: Readonly<Record<Bnd01State, Partial<BinderFilters>>> = {
  a: {},
  c: {},
  d: { season: "TY2026" },
  e: {},
};
