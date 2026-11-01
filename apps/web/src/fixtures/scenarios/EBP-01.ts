// EBP-01 Plan profile & service providers (A-05-T11; A-05 §2.1; the handoff spec): one fixture
// scenario per artboard, each the AUD-02 cockpit with Overview › Plan profile open on Northwind
// PY2025 (seed/ebp01.ts):
//
//   a            marcus-delaney  Thu Sep 24, 10:15 AM  complete
//   b            marcus-delaney  10:15 AM              missing PN: the Form 5500 helper
//   c            marcus-delaney  10:15 AM              provider mismatch: EIN endings, Raise exception…
//   d            marcus-delaney  10:15 AM              edit mode with a sticky Save
//   off          marcus-delaney  10:15 AM              `ebp.modules` off: C-20
//   not_allowed  cole-hart       10:15 AM              walled from Northwind: 404
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
import { type Ebp01Variant, ebp01Plan, ebp01Providers } from "../seed/ebp01";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const AT = "2026-09-24T10:15:00-05:00";
const NOT_FOUND = { detail: "not_found" };
const P = "/v1/audits/{work_item_id}/ebp";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return {
    ...base,
    flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on },
  };
}

export function ebpPlanHandlers(variant: Ebp01Variant): Record<string, FixtureHandler> {
  return {
    [`GET ${P}/plan`]: () => json(ebp01Plan(variant)),
    [`PATCH ${P}/plan`]: () => json(ebp01Plan("a")),
    [`GET ${P}/providers`]: () => json(ebp01Providers(variant)),
  };
}

function walled(): Record<string, FixtureHandler> {
  return {
    [`GET ${P}/plan`]: () => json(NOT_FOUND, 404),
    [`GET ${P}/providers`]: () => json(NOT_FOUND, 404),
  };
}

function frame(
  state: string,
  options: {
    persona?: string;
    variant?: Ebp01Variant;
    on?: boolean;
    reads?: Record<string, FixtureHandler>;
  } = {},
): Scenario {
  const on = options.on ?? true;
  return {
    state,
    persona: options.persona ?? "marcus-delaney",
    clock: AT,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...auditHandlers(seed, "run"),
        "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
        ...(options.reads ?? ebpPlanHandlers(options.variant ?? "a")),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b", { variant: "b" }),
  c: frame("c", { variant: "c" }),
  d: frame("d", { variant: "d" }),
  off: frame("off", { on: false }),
  not_allowed: frame("not_allowed", { persona: "cole-hart", reads: walled() }),
});

export type Ebp01State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp01State[];
