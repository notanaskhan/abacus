// TXP-11: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-11.md), Ridgeline
// Property Partners, LP 2025 Form 1065. Persona, clock and the workbook snapshot follow the
// contract's artboard table; the screen (a later T-05 row) renders them with no network call.
import { defineScenarios } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import { CLOCKS, PERSONAS, type Snapshot } from "../seed/tax-entity";

function at(state: string, clock: keyof typeof CLOCKS, snapshot: Snapshot, proposed = false) {
  return {
    state,
    persona: PERSONAS.olivia,
    clock: CLOCKS[clock],
    handlers: taxEntityHandlers(snapshot, { proposed }),
  };
}

export const scenarios = defineScenarios({
  a: at("a", "e0", "run2"), // Cell selected from issue
  a2: at("a2", "e0", "run2"), // Citation · SHL-07
  a3: at("a3", "e0", "run2"), // Field provenance · SHL-09
  b: at("b", "e0", "run2", true), // Fix proposed
  b2: at("b2", "e0", "afterFix"), // Fix approved
  c: at("c", "e0", "run2"), // 01 Trial Balance
  d: at("d", "e0", "run2"), // Linked evidence · SHL-08
  e: at("e", "e0", "run2"), // Editing
});

export type Txp11State = keyof typeof scenarios;
