// AUD-23's fixture scenarios (A-07-T11; the handoff spec): every artboard's state on the seed. The screen
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
      return { ...E0.handlers, ...completionHandlers({ aud23: state as never }) };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", "hannah-leclerc", "2026-10-07T16:00:00-05:00"),
  b: frame("b", "margaret-okonkwo", "2026-10-07T16:20:00-05:00"),
  c: frame("c", "hannah-leclerc", "2026-10-27T10:00:00-05:00"),
  d: frame("d", "hannah-leclerc", "2026-10-07T16:05:00-05:00"),
  e: frame("e", "hannah-leclerc", "2026-10-07T16:06:00-05:00"),
  f: frame("f", "hannah-leclerc", "2026-10-07T16:07:00-05:00"),
  g: frame("g", "hannah-leclerc", "2026-10-07T16:08:00-05:00"),
  h: frame("h", "margaret-okonkwo", "2026-10-09T16:20:00-05:00"),
  i: frame("i", "hannah-leclerc", "2026-10-09T16:25:00-05:00"),
  j: frame("j", "margaret-okonkwo", "2027-01-15T10:00:00-06:00"),
});

export type State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as State[];
