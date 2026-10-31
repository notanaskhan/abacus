// ADM-08 a–g (T-01-T09 scenarios; built by T-01-T40): one scenario per artboard, and the segment
// or overlay each opens with.
import { scenarios } from "../../fixtures/scenarios/ADM-08";
import type { Adm08Segment } from ".";

export { scenarios };

export type Adm08State = keyof typeof scenarios;

export const OPENS: Readonly<
  Record<Adm08State, { segment: Adm08Segment; mapping?: boolean; test?: boolean }>
> = {
  a: { segment: "tax-engine" },
  b: { segment: "ledgers" },
  c: { segment: "mailboxes" },
  d: { segment: "tax-engine", test: true },
  e: { segment: "ledgers", test: true },
  f: { segment: "tax-engine" },
  g: { segment: "tax-engine", mapping: true },
};

export const STATES = Object.keys(scenarios) as Adm08State[];
