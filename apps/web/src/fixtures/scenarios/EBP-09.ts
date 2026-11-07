// EBP-09 Admin expenses & compliance (A-05-T45; the handoff spec): the fixture scenarios.
//
//   a    marcus-delaney  Thu Sep 24, 10:15 AM  Administrative expenses, agent draft
//   b    marcus-delaney  10:15 AM              Operational compliance
//   c    marcus-delaney  10:15 AM              Plan qualification
//   d    marcus-delaney  10:15 AM              exception variant: no disclosure on file (fixture)
//   e    hannah-leclerc  10:15 AM              consistent, signed: ✓ HL
//   off  marcus-delaney  10:15 AM              `ebp.modules` off: C-20
//
// Dev and test only.

import type { CapabilitiesOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  BUDGET_ACCOUNT,
  COMPLIANCE,
  type Ebp09Variant,
  QUALIFICATION,
  expensesView,
} from "../seed/ebp09";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const E = "/v1/audits/{work_item_id}/ebp";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on } };
}

function frame(
  state: string,
  options: { variant?: Ebp09Variant; persona?: string; on?: boolean } = {},
): Scenario {
  return {
    state,
    persona: options.persona ?? "marcus-delaney",
    clock: "2026-09-24T10:15:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        [`GET ${E}/plan-expenses`]: () => json(expensesView(options.variant ?? "a")),
        [`GET ${E}/erisa-budget-account`]: () => json(BUDGET_ACCOUNT),
        [`GET ${E}/compliance-tests`]: () => json(COMPLIANCE),
        [`GET ${E}/plan-qualification`]: () => json(QUALIFICATION),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: frame("d", { variant: "d" }),
  e: frame("e", { persona: "hannah-leclerc" }),
  off: frame("off", { on: false }),
});

export type Ebp09State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp09State[];
