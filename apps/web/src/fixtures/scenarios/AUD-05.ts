// AUD-05 Narrative workpaper, Risk Assessment (A-04-T21; the handoff spec): one fixture scenario
// per artboard on Northwind PY2025 (seed/aud05.ts):
//
//   a            marcus-delaney    Mon Sep 14, 2:30 PM  Menu 1 and 2, the PBC GAP note
//   b            marcus-delaney    2:30 PM              `?tab=fraud`: minutes awaiting EP approval
//   b_partner    margaret-okonkwo  2:30 PM              `?tab=fraud`: Approve minutes
//   c            marcus-delaney    2:30 PM              Escalate… on the PBC GAP row
//   d            marcus-delaney    4:52 PM              Hannah's L2: "Reviewed · HL"
//   e            marcus-delaney    2:30 PM              Version 2 drafted by the agent (suggested)
//   off          marcus-delaney    2:30 PM              `assurance.risk_register` off: C-20
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
import { type Aud05Variant, aud05Fraud, aud05Record } from "../seed/aud05";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-14T14:30:00-05:00";
const E = "/v1/engagements/{engagement_id}";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "assurance.risk_register": on },
  };
}

function frame(
  state: string,
  options: { persona?: string; variant?: Aud05Variant; on?: boolean; clock?: string } = {},
): Scenario {
  const on = options.on ?? true;
  const persona = options.persona ?? "marcus-delaney";
  return {
    state,
    persona,
    clock: options.clock ?? AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona: who }) => json(capabilities(who, on)),
        [`GET ${E}/workpapers/{workpaper_id}/record`]: () =>
          json(aud05Record(options.variant ?? "a")),
        [`GET ${E}/fraud-brainstorm`]: () => json(aud05Fraud(persona === "margaret-okonkwo")),
        [`POST ${E}/fraud-brainstorm/minutes/approve`]: () =>
          json({
            ...aud05Fraud(true),
            minutes_status: "approved",
            approved_by_name: "Margaret Okonkwo",
            approved_at: AT,
          }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  b_partner: frame("b_partner", { persona: "margaret-okonkwo" }),
  c: frame("c"),
  d: frame("d", { variant: "d", clock: "2026-09-14T16:52:00-05:00" }),
  e: frame("e", { variant: "e" }),
  off: frame("off", { on: false }),
});

export type Aud05State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud05State[];
