// CLI-02 Client record · Overview: one fixture scenario per artboard P-07-T19 builds
// (docs/screens/CLI-02.md). a–e stand at E0, Mon Sep 14, 2026, 9:24 AM CT, seen by Daniel Reyes;
// f at Thu Oct 1, 2026, 10:30 AM CT, seen by Margaret Okonkwo (revision R2). Data:
// fixtures/seed/client-records.ts through fixtures/handlers/client-record.ts. Each artboard is a
// data condition and names the client it opens:
//
//   a   Ridgeline (business): 2 engagements, 11 open issues, 5 waiting, K-1s 2 of 5
//   a2  a with the rail scrolled to Client Portal and Links
//   b   Jonah & Claire Feld (household): SSN masked, MFJ, one 1040 holding a draft Ridgeline K-1
//   c   Northwind Robotics, Inc. (plan sponsor, attest): PBC 11 of 24, run Processing
//   e   Copperleaf Coffee Roasters, Inc. on its onboarding day: no engagements, no sections
//   f   Granite Peak with `insights`: the Client responsiveness card (48% against 63%, 3 overdue)
//
// d (the agent dock answering) is not built here: the dock thread has no API until P-09-T09's
// AgentDockHost, and screens read data only through the generated client (docs/screens/CLI-02.md,
// Deviations). They live under fixtures/ (dev and test only); screens/CLI-02/scenarios.ts
// re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { clientRecordHandlers } from "../handlers/client-record";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  COPPERLEAF,
  FELD,
  GRANITE_PEAK,
  NORTHWIND,
  RIDGELINE,
  clientIdOf,
} from "../seed/client-records";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** Thu Oct 1, 2026, 10:30 AM CT (revision R2 f). */
export const OCT_1 = "2026-10-01T10:30:00-05:00";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const slug = persona ?? "daniel-reyes";
  const base = capabilitiesFor(seed, slug);
  return {
    ...base,
    capabilities: [...base.capabilities, "client.read"],
    entitlements:
      slug === "margaret-okonkwo" ? [...base.entitlements, "insights"] : base.entitlements,
  };
}

function at(
  state: string,
  persona: string,
  clock: string = DEMO_INSTANT,
  handlers: Record<string, FixtureHandler> = {},
): Scenario {
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      ...clientRecordHandlers(seed),
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "daniel-reyes"),
  a2: at("a2", "daniel-reyes"),
  b: at("b", "daniel-reyes"),
  c: at("c", "daniel-reyes"),
  e: at("e", "daniel-reyes"),
  f: at("f", "margaret-okonkwo", OCT_1),
});

export type Cli02State = keyof typeof scenarios;

/** The client each artboard opens. */
export const OPENS: Readonly<Record<Cli02State, string>> = {
  a: clientIdOf(RIDGELINE),
  a2: clientIdOf(RIDGELINE),
  b: clientIdOf(FELD),
  c: clientIdOf(NORTHWIND),
  e: clientIdOf(COPPERLEAF),
  f: clientIdOf(GRANITE_PEAK),
};

/** Grace Holloway, the firm admin: metadata only (ADR-024), so content sections are omitted. */
export function metadataOnlyHandlers(): Record<string, FixtureHandler> {
  return clientRecordHandlers(seed, { metadataOnly: true });
}
