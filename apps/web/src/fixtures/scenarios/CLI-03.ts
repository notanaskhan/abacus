// CLI-03 fixture scenarios (T-06-T23, DEC-5636; docs/screens/CLI-03.md): one per artboard, with the
// contract's persona and demo clock. The scenario seed each artboard names is in its comment;
// every state serves the E0 seed until the screen task's data handlers land (make fixtures).
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";

function at(state: string, persona: string, clock: string): Scenario {
  return { state, persona, clock, handlers: {} };
}

export const scenarios = defineScenarios({
  a: at("a", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // Default graph (Jonah Feld selected; amber banner) · `ridgeline-graph`
  b: at("b", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // List view · `ridgeline-graph`
  c: at("c", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // Trust variant (Calloway Family Trust) · `calloway-graph`
  d: at("d", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // External node (Not a Brightwater Hale client) · `external-node`
  e: at("e", "olivia-brandt", "2026-09-14T09:24:00-05:00"), // Single entity (No relationships yet.) · `single-entity`
  f: at("f", "olivia-brandt", "2026-09-15T10:30:00-05:00"), // After Ridgeline approval (K-1s released Sep 15) · `ridgeline-graph-released`
});

export type Cli03State = keyof typeof scenarios;
