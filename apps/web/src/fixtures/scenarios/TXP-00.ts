// TXP-00: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-00.md), Ridgeline
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
  a: at("a", "e0", "run2"), // Complete with open items
  b: at("b", "afterFix", "run3"), // Running · Run 3
  c: at("c", "idle", "idle"), // Idle · Jun 2
  d: at("d", "run1", "run1"), // Needs input · Run 1, Sep 8
  e: at("e", "run1", "run1"), // Failed task
});

export type Txp00State = keyof typeof scenarios;
