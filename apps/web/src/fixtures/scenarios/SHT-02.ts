// SHT-02 fixture scenarios (K-03-T09; SH-1): the column drawer on BH-FS-430, Hannah Leclerc.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { rows, sheet } from "../seed/sheets-sh1";

function at(state: string, persona: string, clock: string, inUse = false): Scenario {
  return {
    state,
    persona,
    clock,
    handlers: {
      "GET /v1/sheets/{sheet_id}": () => json(sheet("filled")),
      "GET /v1/sheets/{sheet_id}/rows": () => json({ items: rows("filled"), next_cursor: null }),
      "GET /v1/sheets/{sheet_id}/columns/{column_id}/usage": () =>
        json({ filled_rows: inUse ? 40 : 0, views: inUse ? 2 : 0, in_use: inUse }),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "hannah-leclerc", "2026-09-24T11:20:00-05:00"), // New
  b: at("b", "hannah-leclerc", "2026-09-24T11:20:00-05:00"), // Type picker open
  c: at("c", "hannah-leclerc", "2026-09-30T09:50:00-05:00"), // Edit
  d: at("d", "hannah-leclerc", "2026-09-24T11:20:00-05:00"), // Type change warning
  e: at("e", "hannah-leclerc", "2026-09-24T11:20:00-05:00", true), // Blocked delete
  f: at("f", "simone-baptiste", "2026-09-24T11:20:00-05:00"), // Not a manager
});
