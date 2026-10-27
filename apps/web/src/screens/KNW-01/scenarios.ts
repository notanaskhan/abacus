// KNW-01 a–f (K-01-T04): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/KNW-01.ts. Each artboard also names what it opens on.
import { scenarios } from "../../fixtures/scenarios/KNW-01";
import type { KNW01Initial } from ".";

export { scenarios };

export type Knw01State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Knw01State[];

export const OPENS: Readonly<Record<Knw01State, KNW01Initial>> = {
  a: {},
  b: { category: "methodology" },
  c: { tab: "review" },
  d: { tab: "changes" },
  e: {},
  f: { q: "materiality" },
};
