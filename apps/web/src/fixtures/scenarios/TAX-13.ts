// TAX-13 Extensions, estimates & payments (T-03-T11; the handoff spec): the fixture scenarios, Samuel
// Ito at Mon Sep 14, 2026, 9:24 AM CT.
//
//   a   161 extended (79 open + 82 filed) + 2 likely; Ridgeline and Harborview due tomorrow
//   b   TY2026 Q3 installments: Paid 2 · Scheduled 1 · Awaiting 2 = 5 due; Not required 2
//   c   Likely: Lakeshore's Prepare 8868…, Thornbury's Prepare 4768… disabled (G1, G3)
//
// Dev and test only. d and e (the April timeline) are T-03-T16's.

import { type FixtureHandler, type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { tax13Estimates, tax13Extensions } from "../seed/tax13";

const E0 = seedScenario();

function frame(state: string): Scenario {
  return {
    state,
    persona: "samuel-ito",
    clock: "2026-09-14T09:24:00-05:00",
    get handlers(): Record<string, FixtureHandler> {
      return {
        ...E0.handlers,
        "GET /v1/tax/extensions": ({ query }) => json(tax13Extensions(query.get("segment"))),
        "GET /v1/tax/estimates": () => json(tax13Estimates()),
      };
    },
  };
}

export const scenarios = defineScenarios({ a: frame("a"), b: frame("b"), c: frame("c") });
export type Tax13State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Tax13State[];
