// KNW-01 Knowledge library: one fixture scenario per artboard a–f (K-01-T04; KNW-01 handoff, Mon
// Sep 14, 2026, 9:24 AM CT). Data: seed/knowledge.ts through handlers/knowledge.ts. Margaret
// Okonkwo (QM owner) manages and approves content; Ana Cruz (Audit Staff) neither, so the API
// leaves the drafts out for her and the + menu is absent. g and h (the Oct 1 counts and the
// engagement templates) are K-03's and later providers'; they are not built here.
//
//   a  All · Library      b  Methodology      c  Review queue
//   d  Change log         e  Ana Cruz         f  search "materiality"
//
// They live under fixtures/ (dev and test only); src/screens/KNW-01/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { DRAFT_READERS, knowledgeHandlers } from "../handlers/knowledge";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

function capabilities(persona: string): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona);
  const editor = DRAFT_READERS.has(persona);
  return {
    ...base,
    capabilities: [
      ...base.capabilities,
      "knowledge.read",
      ...(editor ? ["methodology.read", "methodology.manage"] : []),
      ...(persona === "margaret-okonkwo" ? ["methodology.approve"] : []),
    ],
    flags: { ...base.flags, "knowledge.catalog": true },
  };
}

function at(state: string, persona = "margaret-okonkwo"): Scenario {
  return {
    state,
    persona,
    clock: DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...knowledgeHandlers(),
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who ?? persona)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e", "ana-cruz"),
  f: at("f"),
});
