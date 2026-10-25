// AUD-01 a–h (A-01-T11): one scenario per artboard (i, the Board, is K-04's). The data and handlers
// live under fixtures/scenarios/AUD-01.ts; each artboard also names the filters it opens on (b the
// Ready to release tile, c Report due │ Next 14 days, e "Pinecrest", h the SOC & IT segment) and
// d the row whose run popover it opens.
import type { AuditFilters } from "../../domain/audits";
import { scenarios } from "../../fixtures/scenarios/AUD-01";

export { scenarios };

export type Aud01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Aud01State[];

/** What each artboard changes from the screen's default filters. */
export const SEARCH: Readonly<Record<Aud01State, Partial<AuditFilters>>> = {
  a: {},
  b: { phase: "ready_to_release" },
  c: { due: "14d" },
  d: {},
  e: { q: "Pinecrest" },
  f: {},
  g: {},
  h: { segment: "soc" },
};

/** Artboards drawn with a popover open: d hovers Northwind's "Processing". */
export const POPOVER: Readonly<Partial<Record<Aud01State, "processing">>> = { d: "processing" };
