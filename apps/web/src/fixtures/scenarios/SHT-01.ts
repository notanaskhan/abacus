// SHT-01 fixture scenarios (K-03-T09; SH-1): BH-FS-430 on Granite Peak FY2026, viewer Cole Hart.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { SHEET_ID, type SheetVariant, rows, sheet } from "../seed/sheets-sh1";

export { SHEET_ID };

function at(state: string, clock: string, v: SheetVariant): Scenario {
  return {
    state,
    persona: "cole-hart",
    clock,
    handlers: {
      "GET /v1/sheets/{sheet_id}": () => json(sheet(v)),
      "GET /v1/sheets/{sheet_id}/rows": () => json({ items: rows(v), next_cursor: null }),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-09-30T10:15:00-05:00", "default"), // Default
  b: at("b", "2026-09-24T10:12:00-05:00", "empty"), // Empty from template
  c: at("c", "2026-09-24T11:10:00-05:00", "filled"), // Filled from the sample
  d: at("d", "2026-09-25T15:20:00-05:00", "running"), // Agent column running
  e: at("e", "2026-09-30T10:15:00-05:00", "default"), // Row drawer · SURL-05
  f: at("f", "2026-10-01T09:00:00-05:00", "locked"), // Locked
});
