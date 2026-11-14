// TXP-01: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-01.md), Ridgeline
// Property Partners, LP 2025 Form 1065. Persona, clock and the workbook snapshot follow the
// contract's artboard table; the screen (a later T-05 row) renders them with no network call.
import { defineScenarios } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import { CLOCKS, PERSONAS, type Snapshot } from "../seed/tax-entity";
import type { MemoState } from "../seed/tax-entity-memo";

function at(state: string, clock: keyof typeof CLOCKS, snapshot: Snapshot, memo: MemoState) {
  return {
    state,
    persona: PERSONAS.samuel,
    clock: CLOCKS[clock],
    handlers: taxEntityHandlers(snapshot, { memo }),
  };
}

export const scenarios = defineScenarios({
  a: at("a", "e0", "run2", "adopted"), // Adopted · awaiting the reviewer
  a2: at("a2", "e0", "run2", "adopted"), // Citation · SHL-07
  a3: at("a3", "e0", "run2", "adopted"), // Sign-off · SHL-12
  b: at("b", "e0", "run2", "drafting"), // Drafting
  c: at("c", "approvedL2", "afterFix", "approved"), // Approved
  d: at("d", "afterFix", "afterFix", "stale"), // Stale
});

export type Txp01State = keyof typeof scenarios;
