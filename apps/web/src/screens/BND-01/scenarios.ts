// BND-01 a–e (P-06-T09, P-06-T16; P-06 §5.4): one scenario per artboard, all at E0, Mon Sep 14,
// 2026, 9:24 AM CT. The data and handlers live under fixtures/scenarios/BND-01.ts; each artboard
// also names the search params it opens on (b: Client activity │ None in 30 days with Fenwick
// selected; d: Season │ TY2026).
import type { BinderFilters } from "../../domain/requests";
import { scenarios as all, fenwickBinderId } from "../../fixtures/scenarios/BND-01";

export const scenarios = { a: all.a, b: all.b, c: all.c, d: all.d, e: all.e };

export type Bnd01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Bnd01State[];

/** What each artboard changes from the screen's default filters. */
export const SEARCH: Readonly<Record<Bnd01State, Partial<BinderFilters>>> = {
  a: {},
  b: { activity: "none_30_days" },
  c: {},
  d: { season: "TY2026" },
  e: {},
};

/** The row an artboard opens selected (b: Fenwick, for a Request Chaser reminder). */
export const SELECTED: Readonly<Partial<Record<Bnd01State, string>>> = { b: fenwickBinderId() };
