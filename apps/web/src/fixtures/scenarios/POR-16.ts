// POR-16 Connections, Copperleaf (A-02-T06; fixture mode for A-02-T18): one scenario per artboard
// a-g (the POR-16 handoff; h and i belong to X-02), each a data condition on
// `GET /v1/portal/entities/{entity_id}/connections`. b and f are a's data with an overlay open
// (the consent sheet for American Express; the disconnect dialog on QuickBooks Online); c and d are
// the reconnect at 9:30 and 9:31 AM; e is QuickBooks' first connect on Wed Mar 4, 2026; g is
// Square's failed sync. Tess Moreno (Owner) throughout.

import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { connectionsHandlers } from "../handlers/connections";
import { portalHandlers } from "../handlers/portal";
import { POR16_CLOCKS, type Por16State } from "../seed/connections";

export interface Por16Artboard {
  /** The overlay open on arrival: the consent sheet or the disconnect dialog, by catalogue key. */
  sheet?: string;
  dialog?: string;
}

const at = (state: Por16State, clock: string = POR16_CLOCKS.a): Scenario => ({
  state,
  persona: "tess-moreno",
  clock,
  handlers: { ...portalHandlers({ clock }), ...connectionsHandlers(state, { clock }) },
});

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c", POR16_CLOCKS.c),
  d: at("d", POR16_CLOCKS.d),
  e: at("e", POR16_CLOCKS.e),
  f: at("f"),
  g: at("g"),
});

export type Por16Scenario = keyof typeof scenarios;

export const ARTBOARD: Readonly<Record<Por16Scenario, Por16Artboard>> = {
  a: {},
  b: { sheet: "american_express" },
  c: {},
  d: {},
  e: { sheet: "quickbooks_online" },
  f: { dialog: "quickbooks_online" },
  g: {},
};
