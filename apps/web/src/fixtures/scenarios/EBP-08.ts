// EBP-08 Participant accounts summary (A-05-T52; the handoff spec): the fixture scenarios.
//
//   a    marcus-delaney  Thu Sep 24, 10:15 AM  agent running (skeleton rows, running pill)
//   b    marcus-delaney  10:15 AM              BrokerWindow
//   c    marcus-delaney  10:15 AM              Vesting
//   d    marcus-delaney  10:21 AM              complete: every tie-out and allocation check ties
//   e    hannah-leclerc  Fri Sep 25            signed off
//   off  marcus-delaney  10:15 AM              `ebp.modules` off
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
import { ROLLFORWARD, SDBA, VESTING } from "../seed/ebp08";
import { capabilitiesFor } from "../seed/shell";

const seed = getSeed();
const E0 = seedScenario();
const E = "/v1/audits/{work_item_id}/ebp/participant-accounts";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return { ...base, flags: { ...base.flags, "audits.cockpit": true, "ebp.modules": on } };
}

function frame(
  state: string,
  options: { persona?: string; on?: boolean; clock?: string } = {},
): Scenario {
  return {
    state,
    persona: options.persona ?? "marcus-delaney",
    clock: options.clock ?? "2026-09-24T10:15:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }) =>
          json(capabilities(persona, options.on ?? true)),
        [`GET ${E}/rollforward`]: () => json(ROLLFORWARD),
        [`GET ${E}/sdba`]: () => json(SDBA),
        [`GET ${E}/vesting`]: () => json(VESTING),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a"),
  b: frame("b"),
  c: frame("c"),
  d: frame("d", { clock: "2026-09-24T10:21:00-05:00" }),
  e: frame("e", { persona: "hannah-leclerc", clock: "2026-09-25T10:00:00-05:00" }),
  off: frame("off", { on: false }),
});

export type Ebp08State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Ebp08State[];
