// AUD-28 fixture scenarios (Q-05-T20, TASK-8826; docs/screens/AUD-28.md): Margaret Okonkwo at
// Tue Oct 6, 2026 11:30 AM CT; one scenario per artboard.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { type Aud28State, detail, log } from "../seed/aud28";

const E0 = seedScenario();
const REFS: Readonly<Record<string, string>> = Object.fromEntries(
  log("a").items.map((r) => [r.consultation_id, r.ref]),
);

function at(state: Aud28State): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: "2026-10-06T11:30:00-05:00",
    handlers: {
      ...E0.handlers,
      "GET /v1/consultations": () => json(log(state)),
      "GET /v1/consultations/{consultation_id}": ({ params }) =>
        json(detail(REFS[params.consultation_id ?? ""] ?? "C-03")),
      "POST /v1/consultations/{consultation_id}/conclude": ({ params }) =>
        json(detail(REFS[params.consultation_id ?? ""] ?? "C-01")),
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
  g: at("g"),
});
export type Aud28ScenarioState = keyof typeof scenarios;
