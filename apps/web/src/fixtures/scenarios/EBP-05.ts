// EBP-05 Distributions & loans (A-05-T44; the handoff spec): the fixture scenarios.
//
//   a    hannah-leclerc  Thu Sep 24, 10:15 AM  Loans, agent draft ready
//   b    hannah-leclerc  10:15 AM              Distributions tab
//   c    hannah-leclerc  10:15 AM              exception variant: comparative off 3,200 (fixture)
//   d    hannah-leclerc  9:52 AM               adopted: ✓ AC
//   e    hannah-leclerc  10:15 AM              signed off: ✓ HL
//   off  hannah-leclerc  10:15 AM              `ebp.modules` off: C-20
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
  type Ebp05Variant,
  OFFSETS,
  NEW_LOANS,
  distributionsGrid,
  loansView,
} from "../seed/ebp05";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const E = "/v1/audits/{work_item_id}/ebp";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "hannah-leclerc");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on } };
}

function frame(
  state: string,
  options: { variant?: Ebp05Variant; clock?: string; on?: boolean } = {},
): Scenario {
  return {
    state,
    persona: "hannah-leclerc",
    clock: options.clock ?? "2026-09-24T10:15:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        [`GET ${E}/loans/rollforward`]: () => json(loansView(options.variant ?? "a")),
        [`GET ${E}/loans/new`]: () => json(NEW_LOANS),
        [`GET ${E}/loans/offsets`]: () => json(OFFSETS),
        [`GET ${E}/distributions/test`]: () => json(distributionsGrid()),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c", { variant: "c" }),
  d: frame("d", { clock: "2026-09-24T09:52:00-05:00" }),
  e: frame("e"),
  off: frame("off", { on: false }),
});

export type Ebp05State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp05State[];
