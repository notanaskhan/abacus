// TXP-06: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-06.md), Ridgeline
// Property Partners, LP 2025 Form 1065. Persona, clock and the workbook snapshot follow the
// contract's artboard table; the screen (a later T-05 row) renders them with no network call.
import { defineScenarios } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import { CLOCKS, PERSONAS, type Snapshot } from "../seed/tax-entity";

function at(state: string, clock: keyof typeof CLOCKS, snapshot: Snapshot) {
  return {
    state,
    persona: PERSONAS.samuel,
    clock: CLOCKS[clock],
    handlers: taxEntityHandlers(snapshot),
  };
}

export const scenarios = defineScenarios({
  a: at("a", "e0", "run2"), // Ridgeline · approved
  a2: at("a2", "e0", "run2"), // Partner series
  b: at("b", "e0", "harborview"), // Harborview · targeted waterfall
  c: at("c", "e0", "run1"), // Pending approval
  c2: at("c2", "e0", "run1"), // Sign off
  d: at("d", "e0", "harborview"), // Editing a rung
});

export type Txp06State = keyof typeof scenarios;
