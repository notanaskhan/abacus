// KNW-06 fixture scenarios (K-03-T08; TV-1): the FS v6 draft at Thu Oct 1, 9:10 AM.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { CHECKS_FAILING, version } from "../seed/templates-v2";

const V = "/v1/template-versions/{version_id}";
function at(state: string, persona: string, failing = false): Scenario {
  return {
    state,
    persona,
    clock: "2026-10-01T09:10:00-05:00",
    handlers: {
      [`GET ${V}`]: () => json(version("v6", "draft")),
      [`GET ${V}/checks`]: () =>
        json(failing ? CHECKS_FAILING : { items: [], errors: 0, warnings: 0 }),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "margaret-okonkwo"), // Drafting
  b: at("b", "margaret-okonkwo"), // Preview mode
  c: at("c", "margaret-okonkwo", true), // Checks failing (2 errors · 1 warning)
  d: at("d", "margaret-okonkwo"), // Request list (41 + 6 by rule)
  e: at("e", "margaret-okonkwo"), // Triggers
  f: at("f", "hannah-leclerc"), // Another viewer (comment, not edit)
});
