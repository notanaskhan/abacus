// AUD-18's fixture scenarios (A-07-T11; the handoff spec): every artboard's state on the seed. The screen
// lands with its row; these exist first so the states are typed and footed. Dev and test only.

import type { FixtureHandler, Scenario } from "../../app-core/fixture-mode";
import { defineScenarios } from "../../app-core/fixture-mode";
import { completionHandlers } from "../handlers/audit-completion";
import { seedScenario } from "../scenario";

const E0 = seedScenario();

function frame(state: string, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers(): Record<string, FixtureHandler> {
      return { ...E0.handlers, ...completionHandlers({ aud18: state as never }) };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", "thomas-whitcombe", "2026-10-05T11:05:00-05:00"),
  b: frame("b", "thomas-whitcombe", "2026-10-05T16:40:00-05:00"),
  b2: frame("b2", "thomas-whitcombe", "2026-10-05T16:40:00-05:00"),
  c: frame("c", "thomas-whitcombe", "2026-10-05T16:41:00-05:00"),
  d: frame("d", "thomas-whitcombe", "2026-10-05T11:05:00-05:00"),
  e: frame("e", "hannah-leclerc", "2026-10-05T11:05:00-05:00"),
});

export type State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as State[];
