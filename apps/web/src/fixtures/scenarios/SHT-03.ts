// SHT-03 fixture scenarios (K-03-T08; TV-1): the FS v6 draft's scoping rules at Thu Oct 1, 8:20 AM.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { scopingPreview, scopingRules } from "../seed/templates-v2";

const V = "/v1/template-versions/{version_id}";
function at(
  state: string,
  rules: ReturnType<typeof scopingRules>,
  as?: "harlow" | "granite",
): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: "2026-10-01T08:20:00-05:00",
    handlers: {
      [`GET ${V}/scoping-rules`]: () => json(rules),
      [`POST ${V}/scoping-rules/preview`]: () => json(scopingPreview(as ?? "harlow")),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", scopingRules(), "harlow"), // Previewing as Harlow & Pike
  b: at("b", scopingRules(), "granite"), // Previewing as Granite Peak
  c: at("c", scopingRules()), // Preview off
  d: at("d", scopingRules(6, true)), // Assertion-level variant (rule 7)
  e: at("e", scopingRules(6, true)), // Conflict (rules 2 and 7)
  f: at("f", scopingRules(0)), // None
});
