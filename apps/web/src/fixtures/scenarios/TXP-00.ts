// TXP-00: one fixture scenario per artboard (T-05-T13; docs/screens/TXP-00.md), Ridgeline
// Property Partners, LP 2025 Form 1065. Persona, clock and the workbook snapshot follow the
// contract's artboard table; the screen (a later T-05 row) renders them with no network call.
import { defineScenarios, json } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import { CLOCKS, PERSONAS, type Snapshot, runs } from "../seed/tax-entity";

/** e: Run 1 stopped at Import trial balance on the expired QuickBooks Online token (T-05-T68). */
function failedRun1() {
  return {
    "GET /v1/tax-returns/{return_id}/workbook-runs": () =>
      json({ items: runs("run1").map((r) => ({ ...r, state: "failed" })) }),
  };
}

function at(state: string, clock: keyof typeof CLOCKS, snapshot: Snapshot) {
  return {
    state,
    persona: PERSONAS.olivia,
    clock: CLOCKS[clock],
    handlers: { ...taxEntityHandlers(snapshot), ...(state === "e" ? failedRun1() : {}) },
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
