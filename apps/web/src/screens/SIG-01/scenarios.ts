// SIG-01's artboards (N-02-T11): each is N-02-T10's scenario plus the screen's own state (the tab
// and the open drawer).
import { scenarios as SIG01_SCENARIOS } from "../../fixtures/scenarios/SIG-01";
import type { Sig01Tab } from ".";

export const STATES = ["a", "b", "c", "d", "e", "f", "g", "r"] as const;
export type Sig01State = (typeof STATES)[number];

export interface Sig01Opens {
  tab: Sig01Tab;
  envelope: string | null;
  checked?: readonly string[];
  importing?: boolean;
}

export const OPENS: Readonly<Record<Sig01State, Sig01Opens>> = {
  a: { tab: "out", envelope: "E2" },
  b: { tab: "to_send", envelope: null },
  c: { tab: "completed", envelope: null },
  d: { tab: "expired", envelope: null },
  e: { tab: "out", envelope: null },
  f: { tab: "out", envelope: null, checked: ["E5", "E8", "E9"] },
  g: { tab: "to_send", envelope: null },
  r: { tab: "out", envelope: null, importing: true },
};

export const scenarios = SIG01_SCENARIOS;
