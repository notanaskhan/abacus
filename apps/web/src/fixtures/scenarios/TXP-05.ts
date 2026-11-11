// TXP-05: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-05.md), Ridgeline
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
  a: at("a", "e0", "run2"), // Federal · as drafted
  a2: at("a2", "e0", "run2"), // Line 2 · Form 8825
  a3: at("a3", "e0", "run2"), // Cell provenance
  a4: at("a4", "e0", "run2"), // Item L off 6,200
  a5: at("a5", "e0", "run2"), // Partner header
  b: at("b", "e0", "run2"), // State K-1 amounts
  c: at("c", "afterFix", "afterFix"), // After the M-2 fix
  d: at("d", "e0", "run2"), // Building
});

export type Txp05State = keyof typeof scenarios;
