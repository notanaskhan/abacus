// CLI-01 Clients index: one fixture scenario per artboard (P-07-T11; docs/screens/CLI-01.md). All
// six stand at E0, Mon Sep 14, 2026, 9:24 AM CT. Data: the 184 clients of the seed through
// fixtures/handlers/clients.ts (`ListPage[ClientRowOut]`); each artboard is a data condition:
//
//   a  Grace Holloway: Status │ Active, 184 clients, the 16 named first, "Load more"
//   b  Grace Holloway: Service line │ Audit → Northwind, Granite Peak, Lakeshore ("Showing 3")
//   c  Lena Park: walled from Ashford, which is simply absent (no footer, count or gap; DEC-43)
//   d  Grace Holloway: q=Schwab matches no client, entity or contact
//   e  Grace Holloway: `GET /v1/clients` never answers (8 skeleton rows)
//   f  Grace Holloway: a firm with no clients (the empty-firm override)
//
// They live under fixtures/ (dev and test only); src/screens/CLI-01/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { clientHandlers } from "../handlers/clients";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** Who may add or import clients (`client.intake`); everyone in the firm reads the list. */
const INTAKE = new Set(["grace-holloway"]);

function capabilities(persona: string | undefined): CapabilitiesOut {
  const slug = persona ?? "grace-holloway";
  const base = capabilitiesFor(seed, slug);
  return {
    ...base,
    capabilities: [
      ...base.capabilities,
      "client.read",
      ...(INTAKE.has(slug) ? ["client.intake"] : []),
    ],
    flags: { ...base.flags, "clients.v2": true },
  };
}

function at(
  state: string,
  persona: string,
  handlers: Record<string, FixtureHandler> = {},
): Scenario {
  return {
    state,
    persona,
    clock: DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "grace-holloway"),
  b: at("b", "grace-holloway"),
  c: at("c", "lena-park"),
  d: at("d", "grace-holloway"),
  e: at("e", "grace-holloway", { "GET /v1/clients": () => never() }),
  f: at("f", "grace-holloway", clientHandlers(seed, { rows: [] })),
});
