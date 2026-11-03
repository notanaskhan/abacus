// AUD-04 Audit program & workpaper, General Audit Planning › Service Organizations (A-04-T27; the
// handoff spec): the fixture scenarios, each on Northwind PY2025 (seed/aud04.ts), Mon Sep 14,
// 2:30 PM CT:
//
//   a  marcus-delaney    the agent's draft: "Draft · Accrued Agent", Sign off… disabled
//   b  marcus-delaney    adopted: "Prepared · MD"
//   c  hannah-leclerc    signed off: "Signed off", ✓ MD ✓ HL
//   d  marcus-delaney    the carve-out cell cites two sources (SHL-07's 1 / 2 stepper)
//   e  marcus-delaney    the Linkage tab
//   f  marcus-delaney    the Audit Approach tab
//
// Dev and test only.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { AUD04_CITATIONS, type Aud04Tab, type Aud04Variant, aud04Record } from "../seed/aud04";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-14T14:30:00-05:00";
const E = "/v1/engagements/{engagement_id}";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true } };
}

function tabOf(raw: string | null): Aud04Tab {
  return raw === "linkage" || raw === "approach" ? raw : "service_organizations";
}

function frame(
  state: string,
  options: { persona?: string; variant?: Aud04Variant } = {},
): Scenario {
  return {
    state,
    persona: options.persona ?? "marcus-delaney",
    clock: AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona)),
        [`GET ${E}/workpapers/{workpaper_id}/record`]: ({ query }) =>
          json(aud04Record(options.variant ?? "a", tabOf(query.get("tab")))),
        "GET /v1/citations": () => json({ items: AUD04_CITATIONS, next_cursor: null }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", { variant: "b" }),
  c: frame("c", { variant: "c", persona: "hannah-leclerc" }),
  d: frame("d"),
  e: frame("e", { variant: "b" }),
  f: frame("f", { variant: "b" }),
});

export type Aud04State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud04State[];

/** The tab each state opens on. */
export const SCENARIO_TAB: Readonly<Record<Aud04State, Aud04Tab>> = {
  a: "service_organizations",
  b: "service_organizations",
  c: "service_organizations",
  d: "service_organizations",
  e: "linkage",
  f: "approach",
};
