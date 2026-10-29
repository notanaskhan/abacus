// ENG-02 Engagement record: one fixture scenario per state P-07-T20 and P-07-T28 build
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
//   a         Copperleaf "2026 Close", Active, CAS: the 12 closes, "7 of 12" (P-07-T28)
//   f         Margaret Okonkwo at Tue Oct 6, 2026, 11:20 AM CT: Granite Peak on the Dashboard tab
//   g         Copperleaf on the Board tab
//
// f and g are fixture-only (their tabs are planned, K-04). They live under fixtures/ (dev and test only);
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
import { engagementRecords, granitePeakOct6 } from "../seed/engagement-records";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const RECORDS = engagementRecords(seed);

function capabilities(persona: string | undefined): CapabilitiesOut {
  return capabilitiesFor(seed, persona ?? "priya-raman");
}

/** f's clock (revision R2): Tue Oct 6, 2026, 11:20 AM CT. */
const OCT_6 = "2026-10-06T11:20:00-05:00";
const GRANITE_PEAK = granitePeakOct6(seed);

function at(
  state: string,
  handlers: Record<string, FixtureHandler> = {},
  options: { persona?: string; clock?: string } = {},
): Scenario {
  return {
    state,
    persona: options.persona ?? "priya-raman",
    clock: options.clock ?? DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...engagementRecordHandlers(seed, state === "f" ? [GRANITE_PEAK] : []),
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
  e: at("e", { "GET /v1/engagements/{engagement_id}/record": () => never() }),
  f: at("f", {}, { persona: "margaret-okonkwo", clock: OCT_6 }),
  g: at("g"),
  prospect: at("prospect"),
});

export type Eng02State = keyof typeof scenarios;

/** The engagement each state opens. */
export const OPENS: Readonly<Record<Eng02State, string>> = {
  a: RECORDS.a.record.id,
  b: RECORDS.b.record.id,
  c: RECORDS.c.record.id,
  d: RECORDS.d.record.id,
  e: RECORDS.b.record.id,
  f: GRANITE_PEAK.record.id,
  g: RECORDS.a.record.id,
  prospect: RECORDS.prospect.record.id,
};

/** The tab each state opens on: f on Dashboard, g on Board (R2); the rest on Overview. */
export const TABS: Readonly<Record<Eng02State, "overview" | "dashboard" | "board">> = {
  a: "overview",
  b: "overview",
  c: "overview",
  d: "overview",
  e: "overview",
  f: "dashboard",
  g: "board",
  prospect: "overview",
};
