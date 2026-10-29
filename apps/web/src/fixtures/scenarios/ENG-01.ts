// ENG-01 Engagements index: one fixture scenario per artboard (P-07-T27; docs/screens/ENG-01.md).
// All five stand at E0, Mon Sep 14, 2026, 9:24 AM CT, seen by Margaret Okonkwo (Managing Partner).
// Data: the ENG-01 slice of the seed (seed/engagement-index.ts) through fixtures/handlers/
// engagements.ts (`EngagementIndexPage`); each artboard is a data condition:
//
//   a  every line, Period │ Current: 273 engagements (archived under Prior, DEC-343), 16 named rows
//   b  Letter │ Not signed with the Accepted tile: rows 4, 6, 7, 9 ("Showing 4 of 4")
//   c  Segment Advisory: the Ridgeline cost segregation & §754 project; Accepted 1, others 0
//   d  q=Harbor Lane matches no engagement or client
//   e  `GET /v1/engagements/index` never answers (skeleton tile counts, 8 skeleton rows)
//
// They live under fixtures/ (dev and test only); src/screens/ENG-01/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();

/** Who may start a new engagement (`engagement.create`: DEC-38's partners; DEC-225). */
const CREATE = new Set(["margaret-okonkwo", "daniel-reyes", "priya-raman"]);

function capabilities(persona: string | undefined): CapabilitiesOut {
  const slug = persona ?? "margaret-okonkwo";
  const base = capabilitiesFor(seed, slug);
  return {
    ...base,
    capabilities: [
      ...base.capabilities,
      "engagement.read_metadata",
      ...(CREATE.has(slug) ? ["engagement.create"] : []),
    ],
  };
}

function at(state: string, handlers: Record<string, FixtureHandler> = {}): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e", { "GET /v1/engagements/index": () => never() }),
});
