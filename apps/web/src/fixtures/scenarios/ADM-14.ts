// ADM-14 fixture scenarios (G-04-T18, DEC-5639; docs/screens/ADM-14.md): Plan & usage at each
// artboard's clock and persona (Grace Holloway, Firm Admin; e is Margaret Okonkwo, Partner,
// read-only). Reads come from `seed/adm14` over the Python export; a Request more answers 201.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { type Adm14State, CLOCKS, alerts, budgets, plan, rates, usage } from "../seed/adm14";

const E0 = seedScenario();

function at(state: Adm14State): Scenario {
  return {
    state,
    persona: state === "e" ? "margaret-okonkwo" : "grace-holloway",
    clock: CLOCKS[state],
    handlers: {
      ...E0.handlers,
      "GET /v1/firm/plan": () => json(plan()),
      "GET /v1/firm/usage": () => json(usage(state)),
      "GET /v1/firm/budget-alerts": () => json(alerts()),
      "GET /v1/firm/engagement-budgets": () => json(budgets()),
      "GET /v1/firm/billing-rates": () => json(rates()),
      "GET /v1/firm/plan-requests": () => json({ items: [], total: 0 }),
      "PUT /v1/firm/budget-alerts": () => json({ ...alerts(), version: 2 }),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  e: at("e"),
  f: at("f"),
});

export type Adm14ScenarioState = keyof typeof scenarios;
