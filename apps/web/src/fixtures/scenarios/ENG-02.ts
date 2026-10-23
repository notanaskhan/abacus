// ENG-02 Engagement record, core: one fixture scenario per state P-07-T20 builds
// (docs/screens/ENG-02.md). All stand at E0, Mon Sep 14, 2026, 9:24 AM CT, seen by Priya Raman
// (revision R2 wins over the spec's Margaret Okonkwo for b). Data:
// fixtures/seed/engagement-records.ts through fixtures/handlers/engagement-record.ts:
//
//   b         Northwind "PY2025 EBP Audit", Active: G1–G3 met, G4 blocked, G5–G9 not started
//   c         Bluestem "2026 Close (from Oct)", Accepted, the letter viewed Sep 11 and not signed
//   d         Meridian "FY2025 FS Audit", Archived, archive locked Jun 12, 2026 (WORM)
//   e         `GET /v1/engagements/{id}/record` never answers
//   prospect  the Thornbury estate engagement, Prospect (spec'd, no artboard)
//
// a, f and g are P-07-T28's. They live under fixtures/ (dev and test only);
// screens/ENG-02/scenarios.ts re-exports them.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { engagementRecordHandlers } from "../handlers/engagement-record";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { engagementRecords } from "../seed/engagement-records";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const RECORDS = engagementRecords(seed);

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "priya-raman");
  return { ...base, flags: { ...base.flags, "engagements.v2": true } };
}

function at(state: string, handlers: Record<string, FixtureHandler> = {}): Scenario {
  return {
    state,
    persona: "priya-raman",
    clock: DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...engagementRecordHandlers(seed),
      "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who)),
      ...handlers,
    },
  };
}

export const scenarios = defineScenarios({
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e", { "GET /v1/engagements/{engagement_id}/record": () => never() }),
  prospect: at("prospect"),
});

export type Eng02State = keyof typeof scenarios;

/** The engagement each state opens. */
export const OPENS: Readonly<Record<Eng02State, string>> = {
  b: RECORDS.b.record.id,
  c: RECORDS.c.record.id,
  d: RECORDS.d.record.id,
  e: RECORDS.b.record.id,
  prospect: RECORDS.prospect.record.id,
};
