// AUD-19's fixture scenarios (A-07-T11; the handoff spec): every artboard's state on the seed. The screen
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
      return { ...E0.handlers, ...completionHandlers({ aud19: state as never }) };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", "hannah-leclerc", "2026-10-07T09:24:00-05:00"),
  a2: frame("a2", "hannah-leclerc", "2026-10-07T09:31:00-05:00"),
  b: frame("b", "hannah-leclerc", "2026-10-07T10:10:00-05:00"),
  c: frame("c", "hannah-leclerc", "2026-10-07T11:00:00-05:00"),
  d: frame("d", "margaret-okonkwo", "2026-10-07T14:20:00-05:00"),
  e: frame("e", "hannah-leclerc", "2026-10-26T10:05:00-05:00"),
  f: frame("f", "hannah-leclerc", "2026-10-09T09:02:00-05:00"),
});

export type State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as State[];
