// AUD-19's fixture scenarios (A-07-T11; the handoff spec): every artboard's state on the seed. The screen
// lands with its row; these exist first so the states are typed and footed. Dev and test only.

import type { FixtureHandler, Scenario } from "../../app-core/fixture-mode";
import { defineScenarios } from "../../app-core/fixture-mode";
import { json } from "../../app-core/fixture-mode";
import { completionHandlers } from "../handlers/audit-completion";
import { aud19Runs } from "../seed/audit-completion";
import { seedScenario } from "../scenario";

const E0 = seedScenario();

function frame(state: string, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        ...completionHandlers({ aud19: state as never }),
        // A-07-T25: the dock's runs #4231 and #4240 (SHL-13 tool cards).
        "GET /v1/engagements/{engagement_id}/agent-runs": () => json(aud19Runs()),
      };
    },
  };
}

export const scenarios = defineScenarios({
  // A-07-T25: clocks and viewers as docs/screens/AUD-19.md (Tue Oct 6, 9:30 AM; e Granite Peak).
  a: frame("a", "hannah-leclerc", "2026-10-06T09:30:00-05:00"),
  a2: frame("a2", "hannah-leclerc", "2026-10-06T09:30:00-05:00"),
  b: frame("b", "hannah-leclerc", "2026-10-06T09:30:00-05:00"),
  c: frame("c", "hannah-leclerc", "2026-10-06T09:30:00-05:00"),
  d: frame("d", "hannah-leclerc", "2026-10-06T09:30:00-05:00"),
  e: frame("e", "margaret-okonkwo", "2026-10-26T10:05:00-05:00"),
  f: frame("f", "hannah-leclerc", "2026-10-09T09:02:00-05:00"),
});

export type State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as State[];
