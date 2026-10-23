// CLI-01 a–f (P-07-T11, T12): one scenario per artboard, all at E0. The data and handlers live
// under fixtures/scenarios/CLI-01.ts; each artboard also names the search it opens on (b opens on
// Service line │ Audit, d on the search "Schwab").
import type { ClientFilters } from "../../domain/clients";
import { scenarios } from "../../fixtures/scenarios/CLI-01";

export { scenarios };

export type Cli01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Cli01State[];

/** What each artboard changes from the screen's default filters. */
export const SEARCH: Readonly<Record<Cli01State, Partial<ClientFilters>>> = {
  a: {},
  b: { serviceLine: "audit" },
  c: {},
  d: { q: "Schwab" },
  e: {},
  f: {},
};
