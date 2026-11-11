// TXP-10: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-10.md), Ridgeline
// Property Partners, LP 2025 Form 1065. Persona, clock and the workbook snapshot follow the
// contract's artboard table; the screen (a later T-05 row) renders them with no network call.
import { defineScenarios } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import { CLOCKS, PERSONAS, type Snapshot } from "../seed/tax-entity";

function at(state: string, clock: keyof typeof CLOCKS, snapshot: Snapshot) {
  return {
    state,
    persona: PERSONAS.olivia,
    clock: CLOCKS[clock],
    handlers: taxEntityHandlers(snapshot),
  };
}

export const scenarios = defineScenarios({
  a: at("a", "e0", "run2"), // Review point
  a2: at("a2", "e0", "run2"), // Approve fix
  b: at("b", "e0", "run2"), // Waiting on the client
  c: at("c", "fixApproved", "run3"), // Agent fixing
  d: at("d", "afterFix", "afterFix"), // Resolved
  e: at("e", "e0", "run2"), // No issue selected
  f: at("f", "e0", "afterFix"), // No open issues
});

export type Txp10State = keyof typeof scenarios;
