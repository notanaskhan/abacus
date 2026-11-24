// ADM-12 fixture scenarios (Q-05-T23, TASK-8933; docs/screens/ADM-12.md): Margaret Okonkwo (QM
// owner) on the 2026 cycle. b and c open the Select engagements and Record finding sheets over a;
// d is Dec 14, 2026 with the Conclude evaluation card; e the empty 2027 cycle; f concluded; g the
// QM-F-02 detail scrolled to its actions.
import {
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  ADM12_CLOCKS,
  type Adm12State,
  candidates,
  evaluation,
  findings,
  inspections,
} from "../seed/adm12";
import { stableId } from "../seed/prng";

const E0 = seedScenario();

function at(state: Adm12State): Scenario {
  return {
    state,
    persona: "margaret-okonkwo",
    clock: ADM12_CLOCKS[state],
    get handlers() {
      let concluded = state === "f";
      return {
        ...E0.handlers,
        "GET /v1/quality/cycles": () =>
          json({
            items: [2026, 2027].map((year) => ({
              cycle_id: stableId(`qm-cycle:${String(year)}`),
              year,
              as_of: `${String(year)}-12-15`,
              planned: year === 2026 ? 2 : 0,
              in_progress: year === 2026 ? 1 : 0,
              concluded: year === 2026 ? 3 : 0,
              findings_open: year === 2026 ? 5 : 0,
            })),
          }),
        "GET /v1/quality/inspections": ({ query }: FixtureRequest) =>
          json({
            items: inspections(query.get("cycle") === "2027" ? 2027 : 2026),
            next_cursor: null,
          }),
        "GET /v1/quality/inspection-candidates": () => json(candidates()),
        "GET /v1/quality/findings": () => json({ items: findings(), next_cursor: null }),
        "GET /v1/quality/findings/{finding_id}": ({ params }: FixtureRequest) =>
          json(findings().find((f) => f.finding_id === params.finding_id) ?? findings()[1]),
        "GET /v1/quality/evaluations/{year}": () =>
          json(evaluation(concluded, concluded || state === "d" ? 0 : 3)),
        "POST /v1/quality/evaluations/{year}/request-conclusion": () => {
          concluded = true;
          return json(evaluation(true));
        },
      };
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
export type Adm12ScenarioState = keyof typeof scenarios;
