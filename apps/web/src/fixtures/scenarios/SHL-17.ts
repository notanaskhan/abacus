// SHL-17 a–f (P-05-T13): one scenario per artboard from the collaboration seed (P-05-T03). a, b
// and c are Northwind (Margaret, then Marcus); d (Tessellate, X-01's host) and e (Granite Peak,
// K-03's host) are fixture-only; f is Marcus's My to-dos at 12:40 PM.
import type { Scenario } from "../../app-core/fixture-mode";
import { defineScenarios } from "../../app-core/fixture-mode";
import { collaborationHandlers } from "../handlers/collaboration";
import { seedScenario } from "../scenario";
import { CLOCKS, PERSONAS, type Shl17State } from "../seed/collaboration";

const E0 = seedScenario();

function frame(state: Shl17State, persona: string, clock: string): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return { ...E0.handlers, ...collaborationHandlers({ shl17: state }) };
    },
  };
}

export const scenarios = defineScenarios({
  a: frame("a", PERSONAS.margaret, CLOCKS.shl17a),
  b: frame("b", PERSONAS.margaret, "2026-09-14T12:35:00-05:00"),
  c: frame("c", PERSONAS.marcus, CLOCKS.shl17c),
  d: frame("d", PERSONAS.kira, CLOCKS.shl17d),
  e: frame("e", PERSONAS.cole, CLOCKS.shl17e),
  f: frame("f", PERSONAS.marcus, CLOCKS.shl17c),
});

export type State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as State[];

// The screen's frames read the collaboration seed through this module (screens may reach only
// their own fixtures/scenarios entry, plan 04 §1.7).
export { NORTHWIND_TEAM, myTodos, todoFor } from "../seed/collaboration";
