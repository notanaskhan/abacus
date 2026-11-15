// CLS-01 a–f (C-01-T33): the data and handlers live under fixtures/scenarios/CLS-01.ts; each
// artboard also names the filters it opens on (b the In progress tile, c Past due, d Attest).
import type { CloseFilters } from "../../domain/closes";
import { type Cls01State, scenarios } from "../../fixtures/scenarios/CLS-01";

export { type Cls01State, scenarios };

export const STATES = Object.keys(scenarios) as Cls01State[];

/** What each artboard changes from the screen's default filters (August 2026). */
export const SEARCH: Readonly<Record<Cls01State, Partial<CloseFilters>>> = {
  a: {},
  b: { status: "in_progress" },
  c: { status: "past_due" },
  d: { attest: true },
  e: {},
  f: {},
};

/** CLS-01 f: the row the interact script hovers. */
export const HOVER_ROW = "Bluebird Bakery Co.";
