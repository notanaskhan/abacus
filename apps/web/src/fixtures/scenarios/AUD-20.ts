// AUD-20 Financial statements & disclosure checklist (A-06-T30; the handoff spec):
//
//   a    hannah-leclerc  Tue Oct 6, 10:40 AM  statements, all tie
//   a2   hannah-leclerc  10:40 AM             Send draft to client… (interact)
//   b    hannah-leclerc  Fri Sep 25           mismatch, draft v1: 62 of 63, RJE-1
//   c    hannah-leclerc  Fri Oct 2            drafting: the skeleton, polling
//   d    hannah-leclerc  10:40 AM             client draft preview: DRAFT, no checklist, no sources
//   e    hannah-leclerc  Thu Oct 8            approved by management
//   f    hannah-leclerc  10:40 AM             Notes tab
//   off  hannah-leclerc  10:40 AM             `reporting.fs_disclosure` off: C-20
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
import { type Aud20Variant, checklistView, statementsView } from "../seed/aud20";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "reporting.fs_disclosure": on },
  };
}

function frame(
  state: string,
  options: { variant?: Aud20Variant; clock?: string; on?: boolean } = {},
): Scenario {
  const variant = options.variant ?? "a";
  return {
    state,
    persona: "hannah-leclerc",
    clock: options.clock ?? "2026-10-06T10:40:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        // A-06-T35: the Evaluation route reads Northwind's cockpit for its audit bar.
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        "GET /v1/engagements/{engagement_id}/financial-statements": () =>
          json(statementsView(variant)),
        "GET /v1/statement-documents/{document_id}/disclosure-checklist": () =>
          json(checklistView()),
        "POST /v1/statement-versions/{version_id}/tie-out": () =>
          json({ statement_version_id: "started" }, 202),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  a2: frame("a2"),
  b: frame("b", { variant: "b", clock: "2026-09-25T10:40:00-05:00" }),
  c: frame("c", { variant: "c", clock: "2026-10-02T15:00:00-05:00" }),
  d: frame("d"),
  e: frame("e", { variant: "e", clock: "2026-10-08T11:00:00-05:00" }),
  f: frame("f"),
  off: frame("off", { on: false }),
});

export type Aud20State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud20State[];
