// WB-10 a–i (W-01-T12): the scenarios are W-01-T03's (fixtures/scenarios/connect.ts); each
// artboard also names what it opens on.
import { scenarios } from "../../fixtures/scenarios/WB-10";
import type { WB10Initial } from ".";

export { scenarios };

export type Wb10State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Wb10State[];

export const OPENS: Readonly<Record<Wb10State, WB10Initial>> = {
  a: {},
  b: { category: "erp" },
  c: { status: "connected" },
  d: {},
  e: {},
  f: {},
  g: { q: "Karbon" },
  h: {},
  i: { category: "grc" },
};
