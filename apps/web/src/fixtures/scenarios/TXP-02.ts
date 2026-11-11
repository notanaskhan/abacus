// TXP-02: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-02.md), Ridgeline
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
  a: at("a", "e0", "run2"), // By Account · Full TB
  a2: at("a2", "e0", "run2"), // Cell provenance
  a3: at("a3", "e0", "run2"), // AJE-1
  b: at("b", "e0", "run2"), // Balance Sheet
  c: at("c", "e0", "run2"), // Income Statement
  d: at("d", "e0", "run2"), // Grouped by Form 1065 Line
  e: at("e", "e0", "run1"), // Unmapped
  e2: at("e2", "e0", "run1"), // Line picker
  f: at("f", "e0", "run2"), // Building
});

export type Txp02State = keyof typeof scenarios;
