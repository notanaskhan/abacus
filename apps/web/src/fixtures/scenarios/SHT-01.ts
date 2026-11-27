// SHT-01 fixture scenarios (K-03-T09; SH-1): BH-FS-430 on Granite Peak FY2026, viewer Cole Hart.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  DRAWER_ROW_KEY,
  SHEET_ID,
  type SheetVariant,
  rowDrawer,
  rowDrawerCitations,
  rowDrawerRun,
  rows,
  sheet,
} from "../seed/sheets-sh1";

export { DRAWER_ROW_KEY, SHEET_ID };

const E0 = seedScenario();

/** K-03-T22: e's drawer reads, on E0 for the comments and to-dos it hosts. */
function drawerAt(clock: string): Scenario {
  const base = at("e", clock, "default");
  return {
    ...base,
    get handlers() {
      return {
        ...E0.handlers,
        ...base.handlers,
        "GET /v1/sheets/{sheet_id}/rows/{row_id}": () => json(rowDrawer()),
        "GET /v1/citations": () =>
          json({ items: rowDrawerCitations(), next_cursor: null, total: 2 }),
        "GET /v1/agent-runs/{run_id}": () => json(rowDrawerRun()),
        "GET /v1/todos": () => json({ items: [], next_cursor: null, total: 0 }),
      };
    },
  };
}

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
  e: drawerAt("2026-09-30T10:15:00-05:00"), // Row drawer · SURL-05 (`?ov=row:SURL-05`)
  f: at("f", "2026-10-01T09:00:00-05:00", "locked"), // Locked
});
