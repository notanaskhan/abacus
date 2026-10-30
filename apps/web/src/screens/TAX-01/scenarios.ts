// TAX-01 a–g (T-02-T12): one scenario per artboard, all at E0. The data and handlers live under
// fixtures/scenarios/TAX-01.ts; each artboard also names the search it opens on.
import { SELECTED_CLIENTS, SELECTED_IDS, scenarios } from "../../fixtures/scenarios/TAX-01";
import type { Tax01Search } from ".";

export { SELECTED_CLIENTS, SELECTED_IDS, scenarios };

export type Tax01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Tax01State[];

/** The URL each artboard opens on (d is a selection made on a's board). */
export const SEARCH: Readonly<Record<Tax01State, Tax01Search>> = {
  a: {},
  b: { tile: "awaiting_signature" },
  c: { office: "grouped" },
  d: {},
  e: { q: "Schwab" },
  f: { tax_year: "2026" },
  g: {},
};
