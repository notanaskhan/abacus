// AUD-01 Audits index: one fixture scenario per artboard (A-01-T11; docs/screens/AUD-01.md). All
// seen by Hannah Leclerc (Audit Senior Manager). a–f stand at E0, Mon Sep 14, 2026, 9:41 AM CT with
// 27 audits; g and h at 10:30 AM in the wave-7 view (E2: A28–A33 and the SOC & IT and Internal
// audit segments, fixture only until A-09, X-01 and X-03 create those types). Data: the AUD-01
// slice of the seed (seed/audits-index.ts) through fixtures/handlers/audits.ts (`AuditIndexPage`);
// each artboard is a data condition:
//
//   a  no filter: 27 rows by phase, then by report due
//   b  phase=ready_to_release (the tile pressed): 2 rows
//   c  due=14d: Sep 18, 21, 25, 28
//   d  Northwind's C6 v1 run summary: "Processing" and its popover (the fixture registers the run
//      provider, so a–c show the pill too; d opens the popover)
//   e  q=Pinecrest matches no row
//   f  `GET /v1/audits` never answers
//   g  E2: 33 rows
//   h  E2 with segment=soc: Tessellate, Larkfield, Brightline
//
// i (Board) is deferred to K-04. They live under fixtures/ (dev and test only);
// src/screens/AUD-01/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { WAVE7_INSTANT } from "../seed/audits-index";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** Mon Sep 14, 2026, 9:41 AM CT: AUD-01 a–f (revision R2, DV-3). */
export const AUD01_INSTANT = "2026-09-14T09:41:00-05:00";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    capabilities: [...base.capabilities, "engagement.read_metadata"],
    flags: { ...base.flags, "audits.cockpit": true },
  };
}

function at(
  state: string,
  epoch: "E0" | "E2",
  handlers: Record<string, FixtureHandler> = {},
): Scenario {
  return {
    state,
    persona: "hannah-leclerc",
    clock: epoch === "E2" ? WAVE7_INSTANT : AUD01_INSTANT,
    handlers: {
      ...E0.handlers,
      ...auditHandlers(seed, "run", { epoch }),
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "E0"),
  b: at("b", "E0"),
  c: at("c", "E0"),
  d: at("d", "E0"),
  e: at("e", "E0"),
  f: at("f", "E0", { "GET /v1/audits": () => never() }),
  g: at("g", "E2"),
  h: at("h", "E2"),
});
