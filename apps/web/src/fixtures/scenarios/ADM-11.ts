// ADM-11 fixture scenarios (Q-05-T19, TASK-8825; docs/screens/ADM-11.md): Margaret Okonkwo (QM
// owner); e is Laura Kemp, Monitoring reviewer, read-only.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  type Adm11State,
  CLOCKS,
  consultationsLog,
  dashboard,
  findings,
  overrides,
  reasons,
  register,
} from "../seed/adm11";

const E0 = seedScenario();

function at(state: Adm11State): Scenario {
  return {
    state,
    persona: state === "e" ? "laura-kemp" : "margaret-okonkwo",
    clock: CLOCKS[state],
    handlers: {
      ...E0.handlers,
      "GET /v1/quality/dashboard": () => json(dashboard(state)),
      "GET /v1/quality/register": () => json(register()),
      "GET /v1/quality/agent-overrides": () => json(overrides()),
      "GET /v1/quality/findings": () => json(findings(state)),
      "GET /v1/quality/agent-overrides/{agent_key}/reasons": () => json(reasons()),
      "GET /v1/audits/consultations": () => json(consultationsLog()),
    },
  };
}

export const scenarios = defineScenarios({ a: at("a"), b: at("b"), c: at("c"), d: at("d"), e: at("e") });
export type Adm11ScenarioState = keyof typeof scenarios;
