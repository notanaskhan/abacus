// ENG-01 a–e (P-07-T27): one scenario per artboard, all at E0. The data and handlers live under
// fixtures/scenarios/ENG-01.ts; each artboard also names the filters it opens on (b opens on
// Letter │ Not signed with the Accepted tile, c on the Advisory segment, d on "Harbor Lane").
import type { EngagementFilters } from "../../domain/engagements";
import { scenarios } from "../../fixtures/scenarios/ENG-01";

export { scenarios };

export type Eng01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Eng01State[];

/** What each artboard changes from the screen's default filters. */
export const SEARCH: Readonly<Record<Eng01State, Partial<EngagementFilters>>> = {
  a: {},
  b: { letter: "not_signed", tile: "accepted" },
  c: { line: "advisory" },
  d: { q: "Harbor Lane" },
  e: {},
};
