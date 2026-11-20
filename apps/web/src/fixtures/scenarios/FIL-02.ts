// FIL-02 fixture scenarios (Q-05-T21, TASK-8827; docs/screens/FIL-02.md).
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { type Fil02State, PERSONA, batch, holds, policies, summary, versions } from "../seed/fil02";

const E0 = seedScenario();

function at(state: Fil02State): Scenario {
  return {
    state,
    persona: PERSONA[state],
    clock: "2026-09-14T09:24:00-05:00",
    handlers: {
      ...E0.handlers,
      "GET /v1/retention/summary": () => json(summary(state)),
      "GET /v1/retention/policies": () => json(policies()),
      "GET /v1/retention/policies/{policy_id}/versions": () => json(versions()),
      "GET /v1/legal-holds": () => json(holds()),
      "GET /v1/destruction-batches": () => json({ items: [batch(state)], next_cursor: null }),
      "GET /v1/destruction-batches/{batch_id}": () => json(batch(state)),
      "POST /v1/destruction-batches/{batch_id}/approvals": () => json(batch("i"), 201),
      "POST /v1/legal-holds": () => json(holds().items[0], 201),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"), b: at("b"), c: at("c"), d: at("d"), e: at("e"), f: at("f"), g: at("g"), h: at("h"), i: at("i"),
});
export type Fil02ScenarioState = keyof typeof scenarios;
