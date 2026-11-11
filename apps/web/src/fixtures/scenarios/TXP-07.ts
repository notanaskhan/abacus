// TXP-07: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-07.md), Ridgeline
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
  a: at("a", "e0", "run2"), // By partner · as drafted
  a2: at("a2", "e0", "run2"), // Tax-exempt cell
  a3: at("a3", "e0", "run2"), // Pell Street transfer
  b: at("b", "e0", "run2"), // By movement
  b2: at("b2", "e0", "run2"), // Sign off · blocked
  c: at("c", "afterFix", "afterFix"), // After the fix
  d: at("d", "e0", "run2"), // Computing
  e: at("e", "afterFix", "afterFix"), // Signed off
});

export type Txp07State = keyof typeof scenarios;
