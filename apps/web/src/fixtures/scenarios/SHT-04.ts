// SHT-04 fixture scenarios (K-03-T09; SH-1): the Conclusion agent column, Fri Sep 25.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { agentColumn, rows, sheet } from "../seed/sheets-sh1";

const A = "/v1/sheets/{sheet_id}/columns/{column_id}/agent";
function at(
  state: string,
  persona: string,
  clock: string,
  status: "draft" | "saved",
  failed = false,
): Scenario {
  return {
    state,
    persona,
    clock,
    handlers: {
      "GET /v1/sheets/{sheet_id}": () => json(sheet(status === "saved" ? "running" : "default")),
      "GET /v1/sheets/{sheet_id}/rows": () => json({ items: rows("default"), next_cursor: null }),
      [`GET ${A}`]: () => json(agentColumn(status)),
      [`POST ${A}/preview`]: () =>
        failed
          ? json({ detail: "missing_reference", facts: { ref: "Receiving date" } }, 422)
          : json({
              preview_id: "00000000-0000-4000-8000-0000000000a4",
              rows: rows("default")
                .slice(0, 3)
                .map((r) => ({
                  row_id: r.row_id,
                  value: r.cells.conclusion?.value ?? "",
                  citation_ids: [],
                })),
            }),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "simone-baptiste", "2026-09-25T14:15:00-05:00", "draft"), // Previewing
  b: at("b", "simone-baptiste", "2026-09-25T14:15:00-05:00", "draft"), // Draft before preview
  c: at("c", "simone-baptiste", "2026-09-25T14:33:00-05:00", "saved"), // Saved and running
  d: at("d", "simone-baptiste", "2026-09-25T14:15:00-05:00", "draft", true), // Failed preview
  e: at("e", "hannah-leclerc", "2026-09-25T14:15:00-05:00", "draft"), // Manager view
});
